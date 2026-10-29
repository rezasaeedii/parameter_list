/**
  ******************************************************************************
  * @file    smart_data.c
  * @brief
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 FAS.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  @verbatim

  @endverbatim
  */

/* Includes ----------------------------------------------------------------- */
#include "smart_data.h"
#include "parameter_descriptor.h"

#include "chrono.h"

/* Private defines ---------------------------------------------------------- */
/* Private macros ----------------------------------------------------------- */
/**
 * @brief Validates that a default value is within the specified range.
 *
 * @param val_ Default value to validate.
 * @param min_ Minimum allowed value.
 * @param max_ Maximum allowed value.
 * @return eSMART_DATA_ERROR_DEFAULT_VALUE_OUT_OF_RANGE if the range
 *         is invalid or the default value is outside the range.
 */
#define ASSERT_DEFAULT_VALUE_(val_, min_, max_)                                                         \
    do {                                                                                                \
        if (((min_) > (max_)) ||                                                                        \
            ((val_) < (min_)) ||                                                                        \
            ((val_) > (max_))) {                                                                        \
            return eSMART_DATA_ERROR_DEFAULT_VALUE_OUT_OF_RANGE;                                        \
        }                                                                                               \
    } while (0)

/**
 * @brief Checks whether a pointer is not NULL.
 *
 * @param ptr_ Pointer to be checked.
 */
#define ASSERT_NOT_NULL_(ptr_)                                                                          \
    do {                                                                                                \
        if(ptr_ == NULL) {                                                                              \
            return eSMART_DATA_ERROR_NULL_POINTER;                                                      \
        }\
    } while(0)

/**
 * @brief Checks whether a value is within the configured smart data range.
 *
 * @note  Written as "not (min <= value <= max)" rather than "value < min or
 *        value > max": the two agree on every number, but a NaN compares false
 *        to everything and so passed the second form, and a NaN in a float
 *        parameter is exactly what a range check is there to keep out.  The
 *        other checks in this file follow the same rule.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pVal_ Pointer to the value to be checked.
 */
#define CHECK_RANGE_(pSd_, pVal_)                                                                       \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pSd_);                                                                         \
        ASSERT_NOT_NULL_(pVal_);                                                                        \
        if((*(pVal_) > (pSd_)->_max) || (*(pVal_) < (pSd_)->_min)) {                                    \
            return eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE;                                                \
        }                                                                                               \
    } while(0)

/**
 * @brief Checks whether a new maximum value is valid for the smart data range.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param max_ New maximum value to be checked.
 */
#define IS_MAX_VALID_(pSd_, max_)                                                                       \
    do {                                                                                                \
        if((max_ < (pSd_)->_min)) {                                                                     \
            return eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE;                                                \
        }                                                                                               \
    } while(0)

/**
 * @brief Checks whether a new minimum value is valid for the smart data range.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param min_ New minimum value to be checked.
 */
#define IS_MIN_VALID_(pSd_, min_)                                                                       \
    do {                                                                                                \
        if((min_ > (pSd_)->_max)) {                                                                     \
            return eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE;                                                \
        }                                                                                               \
    } while(0)

/**
 * @brief Checks whether a user ID is valid.
 *
 * @param userId_ User ID to be checked.
 */
#define CHECK_USER_ID_(userId_)                                                                         \
do {                                                                                                    \
    if ((uint32_t)(userId_) >= (uint32_t)eSMART_DATA_USER_ID_QTY) {                                     \
        return eSMART_DATA_ERROR_INVALID_USER_NUMBER;                                                   \
    }                                                                                                   \
} while (0)

/**
 * @brief Reads the current value of the smart data.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pVal_ Pointer to the output value.
 */
#define READ_(pSd_, pVal_)                                                                              \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pSd_);                                                                         \
        ASSERT_NOT_NULL_(pVal_);                                                                        \
        *pVal_ = (pSd_)->Value;                                                                         \
        (pSd_)->_core.LastReadTimestampUs = (pSd_)->_core.TimestampUs;                                  \
    } while(0)

/**
 * @brief Reads the current value and retrieves its timestamp.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pVal_ Pointer to the output value.
 * @param pTsUs_ Pointer to the output timestamp in microseconds.
 */
#define READ_AND_GET_TIMESTAMP_US_(pSd_, pVal_, pTsUs_)                                                 \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pTsUs_);                                                                       \
        READ_(pSd_, pVal_);                                                                             \
        *(pTsUs_) = (pSd_)->_core.TimestampUs;                                                          \
    } while(0)

/**
 * @brief Reads the smart data only if its value differs from a reference value.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pReferenceValue_ Pointer to the value to compare with - typically the
 *        one the caller read last.
 * @param pVal_ Pointer to the output value.
 */
#define READ_IF_CHANGED_(pSd_, pReferenceValue_, pVal_)                                                 \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pSd_);                                                                         \
        ASSERT_NOT_NULL_(pReferenceValue_);                                                             \
        if(*(pReferenceValue_) != ((pSd_)->Value)) {                                                    \
            READ_(pSd_, pVal_);                                                                         \
        } else {                                                                                        \
            return eSMART_DATA_ERROR_DATA_NOT_CHANGED;                                                  \
        }                                                                                               \
    } while(0)

/**
 * @brief Reads the smart data and its timestamp only if its value differs from
 *        a reference value.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pReferenceValue_ Pointer to the value to compare with.
 * @param pVal_ Pointer to the output value.
 * @param pTsUs_ Pointer to the output timestamp in microseconds.
 */
#define READ_IF_CHANGED_AND_GET_TIMESTAMP_US_(pSd_, pReferenceValue_, pVal_, pTsUs_)                    \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pTsUs_);                                                                       \
        READ_IF_CHANGED_(pSd_, pReferenceValue_, pVal_);                                                \
        *(pTsUs_) = (pSd_)->_core.TimestampUs;                                                          \
    } while(0)

/**
 * @brief Checks if the `ts_` is a newer timestamp than `ref_`.
 *
 * @param ts_ User provided timestamp.
 * @param ref_ Reference to check if ts_ is newer from that.
 * @return isNewer
 */
#define IS_NEWER_(ts_, ref_)  ((int64_t)((uint64_t)(ts_) - (uint64_t)(ref_)) > 0)

/**
 * @brief Reads the smart data only if its timestamp is newer than the specified timestamp.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pVal_ Pointer to the output value.
 * @param timestampUs_ Reference timestamp in microseconds.
 */
#define READ_IF_IS_NEWER_THAN_TIMESTAMP_US_(pSd_, pVal_, timestampUs_)                                  \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pSd_);                                                                         \
        if (IS_NEWER_(pSd_->_core.TimestampUs, timestampUs_)) {                                         \
            READ_(pSd_, pVal_);                                                                         \
        } else {                                                                                        \
            return eSMART_DATA_ERROR_NO_NEW_DATA;                                                       \
        }\
    } while(0)

/**
 * @brief Reads the smart data if its timestamp is newer than the specified timestamp and retrieves its timestamp.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pVal_ Pointer to the output value.
 * @param timestampUs_ Reference timestamp in microseconds.
 * @param pTsUs_ Pointer to the output timestamp in microseconds.
 */
#define READ_IF_IS_NEWER_THAN_TIMESTAMP_US_AND_GET_TIMESTAMP_US_(pSd_, pVal_, timestampUs_, pTsUs_)     \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pTsUs_);                                                                       \
        READ_IF_IS_NEWER_THAN_TIMESTAMP_US_(pSd_, pVal_, timestampUs_);                                 \
        *pTsUs_ = (pSd_)->_core.TimestampUs;                                                            \
    } while(0)

/**
 * @brief Reads the smart data only if it has been updated within the specified duration.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pVal_ Pointer to the output value.
 * @param durationUs_ Maximum allowed age of the data in microseconds.
 */
#define READ_IF_IS_UPDATED_WITHIN_US_(pSd_, pVal_, durationUs_)                                         \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pSd_);                                                                         \
        ASSERT_NOT_NULL_(pVal_);                                                                        \
        if ((fChrono_GetContinuousTickUs() - (pSd_)->_core.TimestampUs) <= (durationUs_)) {             \
            READ_(pSd_, pVal_);                                                                         \
        } else {                                                                                        \
            return eSMART_DATA_ERROR_NO_NEW_DATA;                                                       \
        }                                                                                               \
    } while (0)

/**
 * @brief Reads the smart data if it has been updated within the specified duration and retrieves its timestamp.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pVal_ Pointer to the output value.
 * @param durationUs_ Maximum allowed age of the data in microseconds.
 * @param pTsUs_ Pointer to the output timestamp in microseconds.
 */
#define READ_IF_IS_UPDATED_WITHIN_US_AND_GET_TIMESTAMP_US_(pSd_, pVal_, durationUs_, pTsUs_)            \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pTsUs_);                                                                       \
        READ_IF_IS_UPDATED_WITHIN_US_(pSd_, pVal_, durationUs_);                                        \
        *(pTsUs_) = (pSd_)->_core.TimestampUs;                                                          \
    } while (0)

/**
 * @brief Reads the smart data only if new data is available for the specified user.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pVal_ Pointer to the output value.
 * @param userId_ ID of the user requesting the data.
 */
#define READ_IF_IS_NEW_FOR_ID_(pSd_, pVal_, userId_)                                                    \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pSd_);                                                                         \
        ASSERT_NOT_NULL_(pVal_);                                                                        \
        CHECK_USER_ID_(userId_);                                                                        \
        if (((pSd_)->_core.ReadWriteStatus.UserFlags & (1U << (uint32_t)(userId_))) != 0U) {            \
            READ_(pSd_, pVal_);                                                                         \
            (pSd_)->_core.ReadWriteStatus.UserFlags &= ~(1U << (uint32_t)(userId_));                    \
        } else {                                                                                        \
            return eSMART_DATA_ERROR_NO_NEW_DATA;                                                       \
        }                                                                                               \
    } while (0)

/**
 * @brief Reads the smart data if new data is available for the specified user and retrieves its timestamp.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pVal_ Pointer to the output value.
 * @param userId_ ID of the user requesting the data.
 * @param pTsUs_ Pointer to the output timestamp in microseconds.
 */
#define READ_IF_IS_NEW_FOR_ID_AND_GET_TIMESTAMP_US_(pSd_, pVal_, userId_, pTsUs_)                       \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pTsUs_);                                                                       \
        READ_IF_IS_NEW_FOR_ID_(pSd_, pVal_, userId_);                                                   \
        *(pTsUs_) = (pSd_)->_core.TimestampUs;                                                          \
    } while (0)

/**
 * @brief Writes a value to the smart data using the specified timestamp.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pVal_ Pointer to the value to be written.
 * @param timestampUs_ Timestamp associated with the value in microseconds.
 */
#define WRITE_WITH_TIMESTAMP_US_(pSd_, pVal_, timestampUs_)                                             \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pSd_);                                                                         \
        ASSERT_NOT_NULL_(pVal_);                                                                        \
        (pSd_)->Value = *(pVal_);                                                                       \
        (pSd_)->_core.TimestampUs = (timestampUs_);                                                     \
        (pSd_)->_core.ReadWriteStatus.HasBeenWrittenOnce = TRUE;                                        \
        (pSd_)->_core.ReadWriteStatus.UserFlags = UINT32_MAX;                                           \
    } while (0)

/**
 * @brief Writes a value to the smart data and updates its write status and timestamp.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pVal_ Pointer to the value to be written.
 */
#define WRITE_(pSd_, pVal_) WRITE_WITH_TIMESTAMP_US_(pSd_, pVal_, fChrono_GetContinuousTickUs())

/**
 * @brief Checks whether the smart data has been written at least once.
 *
 * @param pSd_ Pointer to the smart data object.
 * @return TRUE if the smart data has been written at least once; otherwise FALSE.
 */
#define HAS_BEEN_WRITTEN_SO_FAR_(pSd_)                                                                  \
    (((pSd_) != NULL) && ((pSd_)->_core.ReadWriteStatus.HasBeenWrittenOnce == TRUE))

/**
 * @brief Sets the default value of the smart data.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pNewValue_ Pointer to the new default value.
 */
#define SET_DEFAULT_VALUE_(pSd_, pNewValue_)                                                            \
do {                                                                                                    \
    CHECK_RANGE_(pSd_, pNewValue_);                                                                     \
    (pSd_)->_defaultValue = *(pNewValue_);                                                              \
} while (0)

/**
 * @brief Gets the default value of the smart data.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pOutValue_ Pointer to the output default value.
 */
#define GET_DEFAULT_VALUE_(pSd_, pOutValue_)                                                            \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pSd_);                                                                         \
        ASSERT_NOT_NULL_(pOutValue_);                                                                   \
        *(pOutValue_) = (pSd_)->_defaultValue;                                                          \
    } while (0)

/**
 * @brief Gets the timestamp of the smart data.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pOutTimestampUs_ Pointer to the output timestamp in microseconds.
 */
#define GET_TIMESTAMP_(pSd_, pOutTimestampUs_)                                                          \
do {                                                                                                    \
    ASSERT_NOT_NULL_(pSd_);                                                                             \
    ASSERT_NOT_NULL_(pOutTimestampUs_);                                                                 \
    *(pOutTimestampUs_) = (pSd_)->_core.TimestampUs;                                                    \
} while (0)

/**
 * @brief Gets the size of the smart data object.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pOutSize_ Pointer to the output size.
 */
#define GET_SMART_DATA_SIZE_(pSd_, pOutSize_)                                                           \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pSd_);                                                                         \
        ASSERT_NOT_NULL_(pOutSize_);                                                                    \
        *(pOutSize_) = (pSd_)->_core.TypeInfo.SmartDataSize;                                            \
    } while (0)

/**
 * @brief Gets the size of the value stored in the smart data.
 *
 * @param pSd_ Pointer to the smart data object.
 * @param pOutSize_ Pointer to the output value size.
 */
#define GET_VALUE_SIZE_(pSd_, pOutSize_)                                                                \
do {                                                                                                    \
    ASSERT_NOT_NULL_(pSd_);                                                                             \
    ASSERT_NOT_NULL_(pOutSize_);                                                                        \
    *(pOutSize_) = (pSd_)->_core.TypeInfo.ValueSize;                                                    \
} while (0)

/**
 * @brief Validates and sets the minimum value of a Smart Data object.
 *
 * @param pSd_ Smart Data object.
 * @param min_ New minimum value.
 * @return eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE if the new minimum
 *         is greater than the current maximum.
 */
#define SET_MIN_VALUE_(pSd_, min_)                                                                      \
    do {                                                                                                \
        if ((min_) > (pSd_)->_max) {                                                                    \
            return eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE;                                                \
        }                                                                                               \
        (pSd_)->_min = (min_);                                                                          \
    } while (0)

/**
 * @brief Validates and sets the maximum value of a Smart Data object.
 *
 * @param pSd_ Smart Data object.
 * @param max_ New maximum value.
 * @return eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE if the new maximum
 *         is less than the current minimum.
 */
#define SET_MAX_VALUE_(pSd_, max_)                                                                      \
    do {                                                                                                \
        if ((max_) < (pSd_)->_min) {                                                                    \
            return eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE;                                                \
        }                                                                                               \
        (pSd_)->_max = (max_);                                                                          \
    } while (0)

/**
 * @brief Gets the minimum value of a Smart Data object.
 *
 * @param pSd_ Smart Data object.
 * @param pOutValue_ Pointer to the output minimum value.
 */
#define GET_MIN_VALUE_(pSd_, pOutValue_)                                                                \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pSd_);                                                                         \
        ASSERT_NOT_NULL_(pOutValue_);                                                                   \
        *(pOutValue_) = (pSd_)->_min;                                                                   \
    } while (0)

/**
 * @brief Gets the maximum value of a Smart Data object.
 *
 * @param pSd_ Smart Data object.
 * @param pOutValue_ Pointer to the output maximum value.
 */
#define GET_MAX_VALUE_(pSd_, pOutValue_)                                                                \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pSd_);                                                                         \
        ASSERT_NOT_NULL_(pOutValue_);                                                                   \
        *(pOutValue_) = (pSd_)->_max;                                                                   \
    } while (0)

/**
 * @brief Sets the resolution of a Smart Data object.
 *
 * @param pSd_ Smart Data object.
 * @param resolution_ New resolution value.
 */
#define SET_RESOLUTION_(pSd_, resolution_)                                                              \
    do {                                                                                                \
        (pSd_)->_resolution = (resolution_);                                                            \
    } while (0)

/**
 * @brief Gets the resolution of a Smart Data object.
 *
 * @param pSd_ Smart Data object.
 * @param pOutValue_ Pointer to the output resolution value.
 */
#define GET_RESOLUTION_(pSd_, pOutValue_)                                                               \
    do {                                                                                                \
        ASSERT_NOT_NULL_(pSd_);                                                                         \
        ASSERT_NOT_NULL_(pOutValue_);                                                                   \
        *(pOutValue_) = (pSd_)->_resolution;                                                            \
    } while (0)

/**
 * @brief Finds the smart data object of the parameter at an index of the
 *        parameter list, and checks that it is of the expected type.
 *
 * @param index_ Index of the parameter in the parameter list.
 * @param type_ Type the smart data object has to be.
 * @param pSd_ Pointer the smart data object is put in.
 * @return eSMART_DATA_ERROR_NULL_POINTER if there is no parameter at the index,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if its smart data object is
 *         of another type.
 */
#define GET_BY_INDEX_(index_, type_, pSd_)                                                              \
    do {                                                                                                \
        const sParameterDescriptor *pDescriptor_ = fParameterList_GetByIndex(index_);                   \
        if (pDescriptor_ == NULL) {                                                                     \
            return eSMART_DATA_ERROR_NULL_POINTER;                                                      \
        }                                                                                               \
        if (((const sSmartDataCore *)pDescriptor_->pSmartData)->TypeInfo.Type != (type_)) {             \
            return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;                                           \
        }                                                                                               \
        (pSd_) = pDescriptor_->pSmartData;                                                              \
    } while (0)

/* Private types ------------------------------------------------------------ */
/* Private variables -------------------------------------------------------- */
/* Private function prototypes --------------------------------------------- */
/**
 * @brief Returns the descriptor of the parameter at an index of the parameter
 *        list; NULL when the index is out of range.
 *
 * It is defined by the generated parameter list, which is built together with
 * this library; the ...ByIndex functions use it to find a smart data object.
 */
const sParameterDescriptor *fParameterList_GetByIndex(uint16_t index);
/* Private functions -------------------------------------------------------- */
/* Exported variables ------------------------------------------------------- */

/*
  ==============================================================================
                        ##### Exported Functions #####
  ==============================================================================
*/

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                BOOLEAN                                   │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
/**
 * @brief Initializes a B8 smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param defaultVal Initial and default value of the smart data.
 * @return eSmartDataStatus Status of the initialization.
 */
eSmartDataStatus fSmartData_B8_Ctor(sSmartDataB8 * const me, bool_t defaultVal) {

    ASSERT_NOT_NULL_(me);

    me->_core.TypeInfo.Type = eSMART_DATA_TYPE_B8;
    me->_core.TypeInfo.ValueSize = sizeof(bool_t);
    me->_core.TypeInfo.SmartDataSize = sizeof(sSmartDataB8);

    me->_core.TimestampUs = 0x0ULL;
    me->_core.LastReadTimestampUs = 0x0ULL;

    me->_core.ReadWriteStatus.UserFlags = UINT32_MAX;
    me->_core.ReadWriteStatus.HasBeenWrittenOnce = FALSE;

    me->Value = defaultVal;
    me->_defaultValue = defaultVal;

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_B8_Read(sSmartDataB8 * const me, bool_t * pOutValue) {

    READ_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data of the parameter at an
 *        index of the parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a bool_t.
 */
eSmartDataStatus fSmartData_B8_ReadByIndex(uint16_t index, bool_t * pOutValue) {

    sSmartDataB8 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_B8, pSd);

    return fSmartData_B8_Read(pSd, pOutValue);
}

/**
 * @brief Reads the current value and its timestamp from the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_B8_ReadAndGetTimestampUs(sSmartDataB8 * const me, bool_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_AND_GET_TIMESTAMP_US_(me, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_B8_ReadIfChanged(sSmartDataB8 * const me, bool_t * pReferenceValue, bool_t * pOutValue)  {

    READ_IF_CHANGED_(me, pReferenceValue, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_B8_ReadIfChangedAndGetTimestampUs(sSmartDataB8 * const me, bool_t * pReferenceValue, bool_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_IF_CHANGED_AND_GET_TIMESTAMP_US_(me, pReferenceValue, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_B8_ReadIfIsNewerThanTimestampUs(sSmartDataB8 * const me, bool_t * pOutValue, uint64_t timestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_(me, pOutValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_B8_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataB8 * const me, bool_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_AND_GET_TIMESTAMP_US_(me, pOutValue, timestampUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_B8_ReadIfIsUpdatedWithinUs(sSmartDataB8 * const me, bool_t * pOutValue, uint64_t durationUs) {

    READ_IF_IS_UPDATED_WITHIN_US_(me, pOutValue, durationUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_B8_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataB8 * const me, bool_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs) {

        READ_IF_IS_UPDATED_WITHIN_US_AND_GET_TIMESTAMP_US_(me, pOutValue, durationUs, pOutTimestampUs);

        return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_B8_ReadIfIsNewForId(sSmartDataB8 * const me, bool_t * pOutValue, eSmartDataUserId userId){

    READ_IF_IS_NEW_FOR_ID_(me, pOutValue, userId);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_B8_ReadIfIsNewForIdAndGetTimestamp(sSmartDataB8 * const me, bool_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs){

    READ_IF_IS_NEW_FOR_ID_AND_GET_TIMESTAMP_US_(me, pOutValue, userId, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_B8_Write(sSmartDataB8 * const me, bool_t *pValue){

    WRITE_(me, pValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data of the parameter at an index of the
 *        parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a bool_t.
 */
eSmartDataStatus fSmartData_B8_WriteByIndex(uint16_t index, bool_t *pValue) {

    sSmartDataB8 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_B8, pSd);

    return fSmartData_B8_Write(pSd, pValue);
}

/**
 * @brief Writes a value to the smart data with the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @param timestampUs Timestamp associated with the value, in microseconds.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_B8_WriteWithTimestampUs(sSmartDataB8 * const me, bool_t *pValue, uint64_t timestampUs){

    WRITE_WITH_TIMESTAMP_US_(me, pValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Checks whether the smart data has been written at least once.
 *
 * @param me Pointer to the smart data object.
 * @return bool_t TRUE if the smart data has been written at least once, otherwise FALSE.
 */
bool_t fSmartData_B8_HasBeenWrittenSoFar(sSmartDataB8 * const me) {

    return HAS_BEEN_WRITTEN_SO_FAR_(me);
}

/**
 * @brief Sets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_B8_SetDefaultValue(sSmartDataB8 * const me, bool_t * pNewValue) {

    /* Not SET_DEFAULT_VALUE_: that macro range-checks against _min and _max,
       which a boolean does not have - TRUE and FALSE are the whole range. The
       macro therefore did not compile here at all. */
    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    me->_defaultValue = *pNewValue;

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_B8_GetDefaultValue(sSmartDataB8 * const me, bool_t * pOutValue) {

    GET_DEFAULT_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the timestamp of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutTsUs Pointer to the output timestamp.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_B8_GetTimestamp(sSmartDataB8 * const me, uint64_t * pOutTsUs) {

    GET_TIMESTAMP_(me, pOutTsUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_B8_GetSmartDataSize(sSmartDataB8 * const me, size_t * pOutSize) {

    GET_SMART_DATA_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the value stored in the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_B8_GetValueSize(sSmartDataB8 * const me, size_t * pOutSize) {

    GET_VALUE_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                UINT8_T                                   │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
/**
 * @brief Initializes a U8 smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param minVal Minimum allowed value of the smart data.
 * @param maxVal Maximum allowed value of the smart data.
 * @param defaultVal Initial and default value of the smart data.
 * @param resolution Resolution of the smart data.
 * @param pUnit Pointer to the unit string of the smart data.
 * @return eSmartDataStatus Status of the initialization.
 */
eSmartDataStatus fSmartData_U8_Ctor(sSmartDataU8 * const me, uint8_t minVal, uint8_t maxVal, uint8_t defaultVal, uint8_t resolution, const char *pUnit) {

    ASSERT_NOT_NULL_(me);
    ASSERT_DEFAULT_VALUE_(defaultVal, minVal, maxVal);

    me->_core.TypeInfo.Type = eSMART_DATA_TYPE_U8;
    me->_core.TypeInfo.ValueSize = sizeof(uint8_t);
    me->_core.TypeInfo.SmartDataSize = sizeof(sSmartDataU8);

    me->_core.TimestampUs = 0x0ULL;
    me->_core.LastReadTimestampUs = 0x0ULL;

    me->_core.ReadWriteStatus.UserFlags = UINT32_MAX;
    me->_core.ReadWriteStatus.HasBeenWrittenOnce = FALSE;

    me->Value = defaultVal;
    me->_min = minVal;
    me->_max = maxVal;
    me->_defaultValue = defaultVal;
    me->_resolution = resolution;
    me->pUnit = (pUnit == NULL) ? "" : pUnit;

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U8_Read(sSmartDataU8 * const me, uint8_t * pOutValue) {

    READ_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data of the parameter at an
 *        index of the parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a uint8_t.
 */
eSmartDataStatus fSmartData_U8_ReadByIndex(uint16_t index, uint8_t * pOutValue) {

    sSmartDataU8 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_U8, pSd);

    return fSmartData_U8_Read(pSd, pOutValue);
}

/**
 * @brief Reads the current value and its timestamp from the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U8_ReadAndGetTimestampUs(sSmartDataU8 * const me, uint8_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_AND_GET_TIMESTAMP_US_(me, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U8_ReadIfChanged(sSmartDataU8 * const me, uint8_t * pReferenceValue, uint8_t * pOutValue)  {

    READ_IF_CHANGED_(me, pReferenceValue, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U8_ReadIfChangedAndGetTimestampUs(sSmartDataU8 * const me, uint8_t * pReferenceValue, uint8_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_IF_CHANGED_AND_GET_TIMESTAMP_US_(me, pReferenceValue, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U8_ReadIfIsNewerThanTimestampUs(sSmartDataU8 * const me, uint8_t * pOutValue, uint64_t timestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_(me, pOutValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U8_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataU8 * const me, uint8_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_AND_GET_TIMESTAMP_US_(me, pOutValue, timestampUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U8_ReadIfIsUpdatedWithinUs(sSmartDataU8 * const me, uint8_t * pOutValue, uint64_t durationUs) {

    READ_IF_IS_UPDATED_WITHIN_US_(me, pOutValue, durationUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U8_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataU8 * const me, uint8_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_UPDATED_WITHIN_US_AND_GET_TIMESTAMP_US_(me, pOutValue, durationUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U8_ReadIfIsNewForId(sSmartDataU8 * const me, uint8_t * pOutValue, eSmartDataUserId userId){

    READ_IF_IS_NEW_FOR_ID_(me, pOutValue, userId);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U8_ReadIfIsNewForIdAndGetTimestamp(sSmartDataU8 * const me, uint8_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs){

    READ_IF_IS_NEW_FOR_ID_AND_GET_TIMESTAMP_US_(me, pOutValue, userId, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_U8_Write(sSmartDataU8 * const me, uint8_t *pValue){

    CHECK_RANGE_(me, pValue);
    WRITE_(me, pValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data of the parameter at an index of the
 *        parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a uint8_t.
 */
eSmartDataStatus fSmartData_U8_WriteByIndex(uint16_t index, uint8_t *pValue) {

    sSmartDataU8 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_U8, pSd);

    return fSmartData_U8_Write(pSd, pValue);
}

/**
 * @brief Writes a value to the smart data with the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @param timestampUs Timestamp associated with the value, in microseconds.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_U8_WriteWithTimestampUs(sSmartDataU8 * const me, uint8_t *pValue, uint64_t timestampUs){

    CHECK_RANGE_(me, pValue);
    WRITE_WITH_TIMESTAMP_US_(me, pValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Checks whether the smart data has been written at least once.
 *
 * @param me Pointer to the smart data object.
 * @return bool_t TRUE if the smart data has been written at least once, otherwise FALSE.
 */
bool_t fSmartData_U8_HasBeenWrittenSoFar(sSmartDataU8 * const me) {

    return HAS_BEEN_WRITTEN_SO_FAR_(me);
}

/**
 * @brief Verifies the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @return eSmartDataStatus Verification result.
 */
eSmartDataStatus fSmartData_U8_Verify(sSmartDataU8 * const me) {

    ASSERT_NOT_NULL_(me);

    CHECK_RANGE_(me, &(me->Value));

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U8_SetMinValue(sSmartDataU8 * const me, uint8_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MIN_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U8_GetMinValue(sSmartDataU8 * const me, uint8_t * pOutValue) {

    GET_MIN_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U8_SetMaxValue(sSmartDataU8 * const me, uint8_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MAX_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U8_GetMaxValue(sSmartDataU8 * const me, uint8_t * pOutValue) {

    GET_MAX_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U8_SetDefaultValue(sSmartDataU8 * const me, uint8_t * pNewValue) {

    CHECK_RANGE_(me, pNewValue);
    SET_DEFAULT_VALUE_(me, pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U8_GetDefaultValue(sSmartDataU8 * const me, uint8_t * pOutValue) {

    GET_DEFAULT_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U8_SetResolution(sSmartDataU8 * const me, uint8_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_RESOLUTION_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U8_GetResolution(sSmartDataU8 * const me, uint8_t * pOutValue) {

    GET_RESOLUTION_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the timestamp of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutTsUs Pointer to the output timestamp.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U8_GetTimestamp(sSmartDataU8 * const me, uint64_t * pOutTsUs) {

    GET_TIMESTAMP_(me, pOutTsUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U8_GetSmartDataSize(sSmartDataU8 * const me, size_t * pOutSize) {

    GET_SMART_DATA_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the value stored in the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U8_GetValueSize(sSmartDataU8 * const me, size_t * pOutSize) {

    GET_VALUE_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                 INT8_T                                   │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
/**
 * @brief Initializes a I8 smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param minVal Minimum allowed value of the smart data.
 * @param maxVal Maximum allowed value of the smart data.
 * @param defaultVal Initial and default value of the smart data.
 * @param resolution Resolution of the smart data.
 * @param pUnit Pointer to the unit string of the smart data.
 * @return eSmartDataStatus Status of the initialization.
 */
eSmartDataStatus fSmartData_I8_Ctor(sSmartDataI8 * const me, int8_t minVal, int8_t maxVal, int8_t defaultVal, int8_t resolution, const char *pUnit) {

    ASSERT_NOT_NULL_(me);
    ASSERT_DEFAULT_VALUE_(defaultVal, minVal, maxVal);

    me->_core.TypeInfo.Type = eSMART_DATA_TYPE_I8;
    me->_core.TypeInfo.ValueSize = sizeof(int8_t);
    me->_core.TypeInfo.SmartDataSize = sizeof(sSmartDataI8);

    me->_core.TimestampUs = 0x0ULL;
    me->_core.LastReadTimestampUs = 0x0ULL;

    me->_core.ReadWriteStatus.UserFlags = UINT32_MAX;
    me->_core.ReadWriteStatus.HasBeenWrittenOnce = FALSE;

    me->Value = defaultVal;
    me->_min = minVal;
    me->_max = maxVal;
    me->_defaultValue = defaultVal;
    me->_resolution = resolution;
    me->pUnit = (pUnit == NULL) ? "" : pUnit;

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I8_Read(sSmartDataI8 * const me, int8_t * pOutValue) {

    READ_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data of the parameter at an
 *        index of the parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a int8_t.
 */
eSmartDataStatus fSmartData_I8_ReadByIndex(uint16_t index, int8_t * pOutValue) {

    sSmartDataI8 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_I8, pSd);

    return fSmartData_I8_Read(pSd, pOutValue);
}

/**
 * @brief Reads the current value and its timestamp from the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I8_ReadAndGetTimestampUs(sSmartDataI8 * const me, int8_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_AND_GET_TIMESTAMP_US_(me, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I8_ReadIfChanged(sSmartDataI8 * const me, int8_t * pReferenceValue, int8_t * pOutValue)  {

    READ_IF_CHANGED_(me, pReferenceValue, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I8_ReadIfChangedAndGetTimestampUs(sSmartDataI8 * const me, int8_t * pReferenceValue, int8_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_IF_CHANGED_AND_GET_TIMESTAMP_US_(me, pReferenceValue, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I8_ReadIfIsNewerThanTimestampUs(sSmartDataI8 * const me, int8_t * pOutValue, uint64_t timestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_(me, pOutValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I8_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataI8 * const me, int8_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_AND_GET_TIMESTAMP_US_(me, pOutValue, timestampUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I8_ReadIfIsUpdatedWithinUs(sSmartDataI8 * const me, int8_t * pOutValue, uint64_t durationUs) {

    READ_IF_IS_UPDATED_WITHIN_US_(me, pOutValue, durationUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I8_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataI8 * const me, int8_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_UPDATED_WITHIN_US_AND_GET_TIMESTAMP_US_(me, pOutValue, durationUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I8_ReadIfIsNewForId(sSmartDataI8 * const me, int8_t * pOutValue, eSmartDataUserId userId){

    READ_IF_IS_NEW_FOR_ID_(me, pOutValue, userId);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I8_ReadIfIsNewForIdAndGetTimestamp(sSmartDataI8 * const me, int8_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs){

    READ_IF_IS_NEW_FOR_ID_AND_GET_TIMESTAMP_US_(me, pOutValue, userId, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_I8_Write(sSmartDataI8 * const me, int8_t *pValue){

    CHECK_RANGE_(me, pValue);
    WRITE_(me, pValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data of the parameter at an index of the
 *        parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a int8_t.
 */
eSmartDataStatus fSmartData_I8_WriteByIndex(uint16_t index, int8_t *pValue) {

    sSmartDataI8 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_I8, pSd);

    return fSmartData_I8_Write(pSd, pValue);
}

/**
 * @brief Writes a value to the smart data with the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @param timestampUs Timestamp associated with the value, in microseconds.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_I8_WriteWithTimestampUs(sSmartDataI8 * const me, int8_t *pValue, uint64_t timestampUs){

    CHECK_RANGE_(me, pValue);
    WRITE_WITH_TIMESTAMP_US_(me, pValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Checks whether the smart data has been written at least once.
 *
 * @param me Pointer to the smart data object.
 * @return bool_t TRUE if the smart data has been written at least once, otherwise FALSE.
 */
bool_t fSmartData_I8_HasBeenWrittenSoFar(sSmartDataI8 * const me) {

    return HAS_BEEN_WRITTEN_SO_FAR_(me);
}

/**
 * @brief Verifies the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @return eSmartDataStatus Verification result.
 */
eSmartDataStatus fSmartData_I8_Verify(sSmartDataI8 * const me) {

    ASSERT_NOT_NULL_(me);
    CHECK_RANGE_(me, &(me->Value));

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I8_SetMinValue(sSmartDataI8 * const me, int8_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MIN_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I8_GetMinValue(sSmartDataI8 * const me, int8_t * pOutValue) {

    GET_MIN_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I8_SetMaxValue(sSmartDataI8 * const me, int8_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MAX_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I8_GetMaxValue(sSmartDataI8 * const me, int8_t * pOutValue) {

    GET_MAX_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I8_SetDefaultValue(sSmartDataI8 * const me, int8_t * pNewValue) {

    CHECK_RANGE_(me, pNewValue);
    SET_DEFAULT_VALUE_(me, pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I8_GetDefaultValue(sSmartDataI8 * const me, int8_t * pOutValue) {

    GET_DEFAULT_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I8_SetResolution(sSmartDataI8 * const me, int8_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_RESOLUTION_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I8_GetResolution(sSmartDataI8 * const me, int8_t * pOutValue) {

    GET_RESOLUTION_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the timestamp of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutTsUs Pointer to the output timestamp.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I8_GetTimestamp(sSmartDataI8 * const me, uint64_t * pOutTsUs) {

    GET_TIMESTAMP_(me, pOutTsUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I8_GetSmartDataSize(sSmartDataI8 * const me, size_t * pOutSize) {

    GET_SMART_DATA_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the value stored in the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I8_GetValueSize(sSmartDataI8 * const me, size_t * pOutSize) {

    GET_VALUE_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                UINT16_T                                  │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
/**
 * @brief Initializes a U16 smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param minVal Minimum allowed value of the smart data.
 * @param maxVal Maximum allowed value of the smart data.
 * @param defaultVal Initial and default value of the smart data.
 * @param resolution Resolution of the smart data.
 * @param pUnit Pointer to the unit string of the smart data.
 * @return eSmartDataStatus Status of the initialization.
 */
eSmartDataStatus fSmartData_U16_Ctor(sSmartDataU16 * const me, uint16_t minVal, uint16_t maxVal, uint16_t defaultVal, uint16_t resolution, const char *pUnit) {

    ASSERT_NOT_NULL_(me);
    ASSERT_DEFAULT_VALUE_(defaultVal, minVal, maxVal);

    me->_core.TypeInfo.Type = eSMART_DATA_TYPE_U16;
    me->_core.TypeInfo.ValueSize = sizeof(uint16_t);
    me->_core.TypeInfo.SmartDataSize = sizeof(sSmartDataU16);

    me->_core.TimestampUs = 0x0ULL;
    me->_core.LastReadTimestampUs = 0x0ULL;

    me->_core.ReadWriteStatus.UserFlags = UINT32_MAX;
    me->_core.ReadWriteStatus.HasBeenWrittenOnce = FALSE;

    me->Value = defaultVal;
    me->_min = minVal;
    me->_max = maxVal;
    me->_defaultValue = defaultVal;
    me->_resolution = resolution;
    me->pUnit = (pUnit == NULL) ? "" : pUnit;

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U16_Read(sSmartDataU16 * const me, uint16_t * pOutValue) {

    READ_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data of the parameter at an
 *        index of the parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a uint16_t.
 */
eSmartDataStatus fSmartData_U16_ReadByIndex(uint16_t index, uint16_t * pOutValue) {

    sSmartDataU16 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_U16, pSd);

    return fSmartData_U16_Read(pSd, pOutValue);
}

/**
 * @brief Reads the current value and its timestamp from the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U16_ReadAndGetTimestampUs(sSmartDataU16 * const me, uint16_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_AND_GET_TIMESTAMP_US_(me, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U16_ReadIfChanged(sSmartDataU16 * const me, uint16_t * pReferenceValue, uint16_t * pOutValue)  {

    READ_IF_CHANGED_(me, pReferenceValue, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U16_ReadIfChangedAndGetTimestampUs(sSmartDataU16 * const me, uint16_t * pReferenceValue, uint16_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_IF_CHANGED_AND_GET_TIMESTAMP_US_(me, pReferenceValue, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U16_ReadIfIsNewerThanTimestampUs(sSmartDataU16 * const me, uint16_t * pOutValue, uint64_t timestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_(me, pOutValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U16_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataU16 * const me, uint16_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_AND_GET_TIMESTAMP_US_(me, pOutValue, timestampUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U16_ReadIfIsUpdatedWithinUs(sSmartDataU16 * const me, uint16_t * pOutValue, uint64_t durationUs) {

    READ_IF_IS_UPDATED_WITHIN_US_(me, pOutValue, durationUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U16_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataU16 * const me, uint16_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_UPDATED_WITHIN_US_AND_GET_TIMESTAMP_US_(me, pOutValue, durationUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U16_ReadIfIsNewForId(sSmartDataU16 * const me, uint16_t * pOutValue, eSmartDataUserId userId){

    READ_IF_IS_NEW_FOR_ID_(me, pOutValue, userId);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U16_ReadIfIsNewForIdAndGetTimestamp(sSmartDataU16 * const me, uint16_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs){

    READ_IF_IS_NEW_FOR_ID_AND_GET_TIMESTAMP_US_(me, pOutValue, userId, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_U16_Write(sSmartDataU16 * const me, uint16_t *pValue){

    CHECK_RANGE_(me, pValue);
    WRITE_(me, pValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data of the parameter at an index of the
 *        parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a uint16_t.
 */
eSmartDataStatus fSmartData_U16_WriteByIndex(uint16_t index, uint16_t *pValue) {

    sSmartDataU16 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_U16, pSd);

    return fSmartData_U16_Write(pSd, pValue);
}

/**
 * @brief Writes a value to the smart data with the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @param timestampUs Timestamp associated with the value, in microseconds.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_U16_WriteWithTimestampUs(sSmartDataU16 * const me, uint16_t *pValue, uint64_t timestampUs){

    CHECK_RANGE_(me, pValue);
    WRITE_WITH_TIMESTAMP_US_(me, pValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Checks whether the smart data has been written at least once.
 *
 * @param me Pointer to the smart data object.
 * @return bool_t TRUE if the smart data has been written at least once, otherwise FALSE.
 */
bool_t fSmartData_U16_HasBeenWrittenSoFar(sSmartDataU16 * const me) {

    return HAS_BEEN_WRITTEN_SO_FAR_(me);
}

/**
 * @brief Verifies the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @return eSmartDataStatus Verification result.
 */
eSmartDataStatus fSmartData_U16_Verify(sSmartDataU16 * const me) {

    ASSERT_NOT_NULL_(me);
    CHECK_RANGE_(me, &(me->Value));

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U16_SetMinValue(sSmartDataU16 * const me, uint16_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MIN_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U16_GetMinValue(sSmartDataU16 * const me, uint16_t * pOutValue) {

    GET_MIN_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U16_SetMaxValue(sSmartDataU16 * const me, uint16_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MAX_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U16_GetMaxValue(sSmartDataU16 * const me, uint16_t * pOutValue) {

    GET_MAX_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U16_SetDefaultValue(sSmartDataU16 * const me, uint16_t * pNewValue) {

    CHECK_RANGE_(me, pNewValue);
    SET_DEFAULT_VALUE_(me, pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U16_GetDefaultValue(sSmartDataU16 * const me, uint16_t * pOutValue) {

    GET_DEFAULT_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U16_SetResolution(sSmartDataU16 * const me, uint16_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_RESOLUTION_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U16_GetResolution(sSmartDataU16 * const me, uint16_t * pOutValue) {

    GET_RESOLUTION_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the timestamp of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutTsUs Pointer to the output timestamp.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U16_GetTimestamp(sSmartDataU16 * const me, uint64_t * pOutTsUs) {

    GET_TIMESTAMP_(me, pOutTsUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U16_GetSmartDataSize(sSmartDataU16 * const me, size_t * pOutSize) {

    GET_SMART_DATA_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the value stored in the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U16_GetValueSize(sSmartDataU16 * const me, size_t * pOutSize) {

    GET_VALUE_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                INT16_T                                   │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
/**
 * @brief Initializes a I16 smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param minVal Minimum allowed value of the smart data.
 * @param maxVal Maximum allowed value of the smart data.
 * @param defaultVal Initial and default value of the smart data.
 * @param resolution Resolution of the smart data.
 * @param pUnit Pointer to the unit string of the smart data.
 * @return eSmartDataStatus Status of the initialization.
 */
eSmartDataStatus fSmartData_I16_Ctor(sSmartDataI16 * const me, int16_t minVal, int16_t maxVal, int16_t defaultVal, int16_t resolution, const char *pUnit) {

    ASSERT_NOT_NULL_(me);
    ASSERT_DEFAULT_VALUE_(defaultVal, minVal, maxVal);

    me->_core.TypeInfo.Type = eSMART_DATA_TYPE_I16;
    me->_core.TypeInfo.ValueSize = sizeof(int16_t);
    me->_core.TypeInfo.SmartDataSize = sizeof(sSmartDataI16);

    me->_core.TimestampUs = 0x0ULL;
    me->_core.LastReadTimestampUs = 0x0ULL;

    me->_core.ReadWriteStatus.UserFlags = UINT32_MAX;
    me->_core.ReadWriteStatus.HasBeenWrittenOnce = FALSE;

    me->Value = defaultVal;
    me->_min = minVal;
    me->_max = maxVal;
    me->_defaultValue = defaultVal;
    me->_resolution = resolution;
    me->pUnit = (pUnit == NULL) ? "" : pUnit;

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I16_Read(sSmartDataI16 * const me, int16_t * pOutValue) {

    READ_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data of the parameter at an
 *        index of the parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a int16_t.
 */
eSmartDataStatus fSmartData_I16_ReadByIndex(uint16_t index, int16_t * pOutValue) {

    sSmartDataI16 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_I16, pSd);

    return fSmartData_I16_Read(pSd, pOutValue);
}

/**
 * @brief Reads the current value and its timestamp from the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I16_ReadAndGetTimestampUs(sSmartDataI16 * const me, int16_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_AND_GET_TIMESTAMP_US_(me, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I16_ReadIfChanged(sSmartDataI16 * const me, int16_t * pReferenceValue, int16_t * pOutValue)  {

    READ_IF_CHANGED_(me, pReferenceValue, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I16_ReadIfChangedAndGetTimestampUs(sSmartDataI16 * const me, int16_t * pReferenceValue, int16_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_IF_CHANGED_AND_GET_TIMESTAMP_US_(me, pReferenceValue, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I16_ReadIfIsNewerThanTimestampUs(sSmartDataI16 * const me, int16_t * pOutValue, uint64_t timestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_(me, pOutValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I16_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataI16 * const me, int16_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_AND_GET_TIMESTAMP_US_(me, pOutValue, timestampUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I16_ReadIfIsUpdatedWithinUs(sSmartDataI16 * const me, int16_t * pOutValue, uint64_t durationUs) {

    READ_IF_IS_UPDATED_WITHIN_US_(me, pOutValue, durationUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I16_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataI16 * const me, int16_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_UPDATED_WITHIN_US_AND_GET_TIMESTAMP_US_(me, pOutValue, durationUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I16_ReadIfIsNewForId(sSmartDataI16 * const me, int16_t * pOutValue, eSmartDataUserId userId){

    READ_IF_IS_NEW_FOR_ID_(me, pOutValue, userId);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I16_ReadIfIsNewForIdAndGetTimestamp(sSmartDataI16 * const me, int16_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs){

    READ_IF_IS_NEW_FOR_ID_AND_GET_TIMESTAMP_US_(me, pOutValue, userId, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_I16_Write(sSmartDataI16 * const me, int16_t *pValue){

    CHECK_RANGE_(me, pValue);
    WRITE_(me, pValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data of the parameter at an index of the
 *        parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a int16_t.
 */
eSmartDataStatus fSmartData_I16_WriteByIndex(uint16_t index, int16_t *pValue) {

    sSmartDataI16 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_I16, pSd);

    return fSmartData_I16_Write(pSd, pValue);
}

/**
 * @brief Writes a value to the smart data with the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @param timestampUs Timestamp associated with the value, in microseconds.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_I16_WriteWithTimestampUs(sSmartDataI16 * const me, int16_t *pValue, uint64_t timestampUs){

    CHECK_RANGE_(me, pValue);
    WRITE_WITH_TIMESTAMP_US_(me, pValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Checks whether the smart data has been written at least once.
 *
 * @param me Pointer to the smart data object.
 * @return bool_t TRUE if the smart data has been written at least once, otherwise FALSE.
 */
bool_t fSmartData_I16_HasBeenWrittenSoFar(sSmartDataI16 * const me) {

    return HAS_BEEN_WRITTEN_SO_FAR_(me);
}

/**
 * @brief Verifies the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @return eSmartDataStatus Verification result.
 */
eSmartDataStatus fSmartData_I16_Verify(sSmartDataI16 * const me) {

    ASSERT_NOT_NULL_(me);
    CHECK_RANGE_(me, &(me->Value));

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I16_SetMinValue(sSmartDataI16 * const me, int16_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MIN_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I16_GetMinValue(sSmartDataI16 * const me, int16_t * pOutValue) {

    GET_MIN_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I16_SetMaxValue(sSmartDataI16 * const me, int16_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MAX_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I16_GetMaxValue(sSmartDataI16 * const me, int16_t * pOutValue) {

    GET_MAX_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I16_SetDefaultValue(sSmartDataI16 * const me, int16_t * pNewValue) {

    CHECK_RANGE_(me, pNewValue);
    SET_DEFAULT_VALUE_(me, pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I16_GetDefaultValue(sSmartDataI16 * const me, int16_t * pOutValue) {

    GET_DEFAULT_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I16_SetResolution(sSmartDataI16 * const me, int16_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_RESOLUTION_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I16_GetResolution(sSmartDataI16 * const me, int16_t * pOutValue) {

    GET_RESOLUTION_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the timestamp of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutTsUs Pointer to the output timestamp.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I16_GetTimestamp(sSmartDataI16 * const me, uint64_t * pOutTsUs) {

    GET_TIMESTAMP_(me, pOutTsUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I16_GetSmartDataSize(sSmartDataI16 * const me, size_t * pOutSize) {

    GET_SMART_DATA_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the value stored in the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I16_GetValueSize(sSmartDataI16 * const me, size_t * pOutSize) {

    GET_VALUE_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                               UINT32_T                                   │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
/**
 * @brief Initializes a U32 smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param minVal Minimum allowed value of the smart data.
 * @param maxVal Maximum allowed value of the smart data.
 * @param defaultVal Initial and default value of the smart data.
 * @param resolution Resolution of the smart data.
 * @param pUnit Pointer to the unit string of the smart data.
 * @return eSmartDataStatus Status of the initialization.
 */
eSmartDataStatus fSmartData_U32_Ctor(sSmartDataU32 * const me, uint32_t minVal, uint32_t maxVal, uint32_t defaultVal, uint32_t resolution, const char *pUnit) {

    ASSERT_NOT_NULL_(me);
    ASSERT_DEFAULT_VALUE_(defaultVal, minVal, maxVal);

    me->_core.TypeInfo.Type = eSMART_DATA_TYPE_U32;
    me->_core.TypeInfo.ValueSize = sizeof(uint32_t);
    me->_core.TypeInfo.SmartDataSize = sizeof(sSmartDataU32);

    me->_core.TimestampUs = 0x0ULL;
    me->_core.LastReadTimestampUs = 0x0ULL;

    me->_core.ReadWriteStatus.UserFlags = UINT32_MAX;
    me->_core.ReadWriteStatus.HasBeenWrittenOnce = FALSE;

    me->Value = defaultVal;
    me->_min = minVal;
    me->_max = maxVal;
    me->_defaultValue = defaultVal;
    me->_resolution = resolution;
    me->pUnit = (pUnit == NULL) ? "" : pUnit;

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U32_Read(sSmartDataU32 * const me, uint32_t * pOutValue) {

    READ_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data of the parameter at an
 *        index of the parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a uint32_t.
 */
eSmartDataStatus fSmartData_U32_ReadByIndex(uint16_t index, uint32_t * pOutValue) {

    sSmartDataU32 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_U32, pSd);

    return fSmartData_U32_Read(pSd, pOutValue);
}

/**
 * @brief Reads the current value and its timestamp from the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U32_ReadAndGetTimestampUs(sSmartDataU32 * const me, uint32_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_AND_GET_TIMESTAMP_US_(me, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U32_ReadIfChanged(sSmartDataU32 * const me, uint32_t * pReferenceValue, uint32_t * pOutValue)  {

    READ_IF_CHANGED_(me, pReferenceValue, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U32_ReadIfChangedAndGetTimestampUs(sSmartDataU32 * const me, uint32_t * pReferenceValue, uint32_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_IF_CHANGED_AND_GET_TIMESTAMP_US_(me, pReferenceValue, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U32_ReadIfIsNewerThanTimestampUs(sSmartDataU32 * const me, uint32_t * pOutValue, uint64_t timestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_(me, pOutValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U32_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataU32 * const me, uint32_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_AND_GET_TIMESTAMP_US_(me, pOutValue, timestampUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U32_ReadIfIsUpdatedWithinUs(sSmartDataU32 * const me, uint32_t * pOutValue, uint64_t durationUs) {

    READ_IF_IS_UPDATED_WITHIN_US_(me, pOutValue, durationUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U32_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataU32 * const me, uint32_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_UPDATED_WITHIN_US_AND_GET_TIMESTAMP_US_(me, pOutValue, durationUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U32_ReadIfIsNewForId(sSmartDataU32 * const me, uint32_t * pOutValue, eSmartDataUserId userId){

    READ_IF_IS_NEW_FOR_ID_(me, pOutValue, userId);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U32_ReadIfIsNewForIdAndGetTimestamp(sSmartDataU32 * const me, uint32_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs){

    READ_IF_IS_NEW_FOR_ID_AND_GET_TIMESTAMP_US_(me, pOutValue, userId, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_U32_Write(sSmartDataU32 * const me, uint32_t *pValue){

    CHECK_RANGE_(me, pValue);
    WRITE_(me, pValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data of the parameter at an index of the
 *        parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a uint32_t.
 */
eSmartDataStatus fSmartData_U32_WriteByIndex(uint16_t index, uint32_t *pValue) {

    sSmartDataU32 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_U32, pSd);

    return fSmartData_U32_Write(pSd, pValue);
}

/**
 * @brief Writes a value to the smart data with the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @param timestampUs Timestamp associated with the value, in microseconds.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_U32_WriteWithTimestampUs(sSmartDataU32 * const me, uint32_t *pValue, uint64_t timestampUs){

    CHECK_RANGE_(me, pValue);
    WRITE_WITH_TIMESTAMP_US_(me, pValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Checks whether the smart data has been written at least once.
 *
 * @param me Pointer to the smart data object.
 * @return bool_t TRUE if the smart data has been written at least once, otherwise FALSE.
 */
bool_t fSmartData_U32_HasBeenWrittenSoFar(sSmartDataU32 * const me) {

    return HAS_BEEN_WRITTEN_SO_FAR_(me);
}

/**
 * @brief Verifies the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @return eSmartDataStatus Verification result.
 */
eSmartDataStatus fSmartData_U32_Verify(sSmartDataU32 * const me) {

    ASSERT_NOT_NULL_(me);
    CHECK_RANGE_(me, &(me->Value));

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U32_SetMinValue(sSmartDataU32 * const me, uint32_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MIN_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U32_GetMinValue(sSmartDataU32 * const me, uint32_t * pOutValue) {

    GET_MIN_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U32_SetMaxValue(sSmartDataU32 * const me, uint32_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MAX_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U32_GetMaxValue(sSmartDataU32 * const me, uint32_t * pOutValue) {

    GET_MAX_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U32_SetDefaultValue(sSmartDataU32 * const me, uint32_t * pNewValue) {

    CHECK_RANGE_(me, pNewValue);
    SET_DEFAULT_VALUE_(me, pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U32_GetDefaultValue(sSmartDataU32 * const me, uint32_t * pOutValue) {

    GET_DEFAULT_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U32_SetResolution(sSmartDataU32 * const me, uint32_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_RESOLUTION_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U32_GetResolution(sSmartDataU32 * const me, uint32_t * pOutValue) {

    GET_RESOLUTION_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the timestamp of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutTsUs Pointer to the output timestamp.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U32_GetTimestamp(sSmartDataU32 * const me, uint64_t * pOutTsUs) {

    GET_TIMESTAMP_(me, pOutTsUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U32_GetSmartDataSize(sSmartDataU32 * const me, size_t * pOutSize) {

    GET_SMART_DATA_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the value stored in the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U32_GetValueSize(sSmartDataU32 * const me, size_t * pOutSize) {

    GET_VALUE_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                INT32_T                                   │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
/**
 * @brief Initializes a I32 smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param minVal Minimum allowed value of the smart data.
 * @param maxVal Maximum allowed value of the smart data.
 * @param defaultVal Initial and default value of the smart data.
 * @param resolution Resolution of the smart data.
 * @param pUnit Pointer to the unit string of the smart data.
 * @return eSmartDataStatus Status of the initialization.
 */
eSmartDataStatus fSmartData_I32_Ctor(sSmartDataI32 * const me, int32_t minVal, int32_t maxVal, int32_t defaultVal, int32_t resolution, const char *pUnit) {

    ASSERT_NOT_NULL_(me);
    ASSERT_DEFAULT_VALUE_(defaultVal, minVal, maxVal);

    me->_core.TypeInfo.Type = eSMART_DATA_TYPE_I32;
    me->_core.TypeInfo.ValueSize = sizeof(int32_t);
    me->_core.TypeInfo.SmartDataSize = sizeof(sSmartDataI32);

    me->_core.TimestampUs = 0x0ULL;
    me->_core.LastReadTimestampUs = 0x0ULL;

    me->_core.ReadWriteStatus.UserFlags = UINT32_MAX;
    me->_core.ReadWriteStatus.HasBeenWrittenOnce = FALSE;

    me->Value = defaultVal;
    me->_min = minVal;
    me->_max = maxVal;
    me->_defaultValue = defaultVal;
    me->_resolution = resolution;
    me->pUnit = (pUnit == NULL) ? "" : pUnit;

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I32_Read(sSmartDataI32 * const me, int32_t * pOutValue) {

    READ_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data of the parameter at an
 *        index of the parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a int32_t.
 */
eSmartDataStatus fSmartData_I32_ReadByIndex(uint16_t index, int32_t * pOutValue) {

    sSmartDataI32 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_I32, pSd);

    return fSmartData_I32_Read(pSd, pOutValue);
}

/**
 * @brief Reads the current value and its timestamp from the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I32_ReadAndGetTimestampUs(sSmartDataI32 * const me, int32_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_AND_GET_TIMESTAMP_US_(me, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I32_ReadIfChanged(sSmartDataI32 * const me, int32_t * pReferenceValue, int32_t * pOutValue)  {

    READ_IF_CHANGED_(me, pReferenceValue, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I32_ReadIfChangedAndGetTimestampUs(sSmartDataI32 * const me, int32_t * pReferenceValue, int32_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_IF_CHANGED_AND_GET_TIMESTAMP_US_(me, pReferenceValue, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I32_ReadIfIsNewerThanTimestampUs(sSmartDataI32 * const me, int32_t * pOutValue, uint64_t timestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_(me, pOutValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I32_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataI32 * const me, int32_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_AND_GET_TIMESTAMP_US_(me, pOutValue, timestampUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I32_ReadIfIsUpdatedWithinUs(sSmartDataI32 * const me, int32_t * pOutValue, uint64_t durationUs) {

    READ_IF_IS_UPDATED_WITHIN_US_(me, pOutValue, durationUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I32_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataI32 * const me, int32_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_UPDATED_WITHIN_US_AND_GET_TIMESTAMP_US_(me, pOutValue, durationUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I32_ReadIfIsNewForId(sSmartDataI32 * const me, int32_t * pOutValue, eSmartDataUserId userId){

    READ_IF_IS_NEW_FOR_ID_(me, pOutValue, userId);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I32_ReadIfIsNewForIdAndGetTimestamp(sSmartDataI32 * const me, int32_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs){

    READ_IF_IS_NEW_FOR_ID_AND_GET_TIMESTAMP_US_(me, pOutValue, userId, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_I32_Write(sSmartDataI32 * const me, int32_t *pValue){

    CHECK_RANGE_(me, pValue);
    WRITE_(me, pValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data of the parameter at an index of the
 *        parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a int32_t.
 */
eSmartDataStatus fSmartData_I32_WriteByIndex(uint16_t index, int32_t *pValue) {

    sSmartDataI32 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_I32, pSd);

    return fSmartData_I32_Write(pSd, pValue);
}

/**
 * @brief Writes a value to the smart data with the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @param timestampUs Timestamp associated with the value, in microseconds.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_I32_WriteWithTimestampUs(sSmartDataI32 * const me, int32_t *pValue, uint64_t timestampUs){

    CHECK_RANGE_(me, pValue);
    WRITE_WITH_TIMESTAMP_US_(me, pValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Checks whether the smart data has been written at least once.
 *
 * @param me Pointer to the smart data object.
 * @return bool_t TRUE if the smart data has been written at least once, otherwise FALSE.
 */
bool_t fSmartData_I32_HasBeenWrittenSoFar(sSmartDataI32 * const me) {

    return HAS_BEEN_WRITTEN_SO_FAR_(me);
}

/**
 * @brief Verifies the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @return eSmartDataStatus Verification result.
 */
eSmartDataStatus fSmartData_I32_Verify(sSmartDataI32 * const me) {

    ASSERT_NOT_NULL_(me);
    CHECK_RANGE_(me, &(me->Value));

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I32_SetMinValue(sSmartDataI32 * const me, int32_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MIN_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I32_GetMinValue(sSmartDataI32 * const me, int32_t * pOutValue) {

    GET_MIN_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I32_SetMaxValue(sSmartDataI32 * const me, int32_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MAX_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I32_GetMaxValue(sSmartDataI32 * const me, int32_t * pOutValue) {

    GET_MAX_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I32_SetDefaultValue(sSmartDataI32 * const me, int32_t * pNewValue) {

    CHECK_RANGE_(me, pNewValue);
    SET_DEFAULT_VALUE_(me, pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I32_GetDefaultValue(sSmartDataI32 * const me, int32_t * pOutValue) {

    GET_DEFAULT_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I32_SetResolution(sSmartDataI32 * const me, int32_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_RESOLUTION_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I32_GetResolution(sSmartDataI32 * const me, int32_t * pOutValue) {

    GET_RESOLUTION_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the timestamp of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutTsUs Pointer to the output timestamp.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I32_GetTimestamp(sSmartDataI32 * const me, uint64_t * pOutTsUs) {

    GET_TIMESTAMP_(me, pOutTsUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I32_GetSmartDataSize(sSmartDataI32 * const me, size_t * pOutSize) {

    GET_SMART_DATA_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the value stored in the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I32_GetValueSize(sSmartDataI32 * const me, size_t * pOutSize) {

    GET_VALUE_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                               UINT64_T                                   │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
/**
 * @brief Initializes a U64 smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param minVal Minimum allowed value of the smart data.
 * @param maxVal Maximum allowed value of the smart data.
 * @param defaultVal Initial and default value of the smart data.
 * @param resolution Resolution of the smart data.
 * @param pUnit Pointer to the unit string of the smart data.
 * @return eSmartDataStatus Status of the initialization.
 */
eSmartDataStatus fSmartData_U64_Ctor(sSmartDataU64 * const me, uint64_t minVal, uint64_t maxVal, uint64_t defaultVal, uint64_t resolution, const char *pUnit) {

    ASSERT_NOT_NULL_(me);
    ASSERT_DEFAULT_VALUE_(defaultVal, minVal, maxVal);

    me->_core.TypeInfo.Type = eSMART_DATA_TYPE_U64;
    me->_core.TypeInfo.ValueSize = sizeof(uint64_t);
    me->_core.TypeInfo.SmartDataSize = sizeof(sSmartDataU64);

    me->_core.TimestampUs = 0x0ULL;
    me->_core.LastReadTimestampUs = 0x0ULL;

    me->_core.ReadWriteStatus.UserFlags = UINT32_MAX;
    me->_core.ReadWriteStatus.HasBeenWrittenOnce = FALSE;

    me->Value = defaultVal;
    me->_min = minVal;
    me->_max = maxVal;
    me->_defaultValue = defaultVal;
    me->_resolution = resolution;
    me->pUnit = (pUnit == NULL) ? "" : pUnit;

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U64_Read(sSmartDataU64 * const me, uint64_t * pOutValue) {

    READ_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data of the parameter at an
 *        index of the parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a uint64_t.
 */
eSmartDataStatus fSmartData_U64_ReadByIndex(uint16_t index, uint64_t * pOutValue) {

    sSmartDataU64 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_U64, pSd);

    return fSmartData_U64_Read(pSd, pOutValue);
}

/**
 * @brief Reads the current value and its timestamp from the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U64_ReadAndGetTimestampUs(sSmartDataU64 * const me, uint64_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_AND_GET_TIMESTAMP_US_(me, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U64_ReadIfChanged(sSmartDataU64 * const me, uint64_t * pReferenceValue, uint64_t * pOutValue)  {

    READ_IF_CHANGED_(me, pReferenceValue, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U64_ReadIfChangedAndGetTimestampUs(sSmartDataU64 * const me, uint64_t * pReferenceValue, uint64_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_IF_CHANGED_AND_GET_TIMESTAMP_US_(me, pReferenceValue, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U64_ReadIfIsNewerThanTimestampUs(sSmartDataU64 * const me, uint64_t * pOutValue, uint64_t timestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_(me, pOutValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U64_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataU64 * const me, uint64_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_AND_GET_TIMESTAMP_US_(me, pOutValue, timestampUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U64_ReadIfIsUpdatedWithinUs(sSmartDataU64 * const me, uint64_t * pOutValue, uint64_t durationUs) {

    READ_IF_IS_UPDATED_WITHIN_US_(me, pOutValue, durationUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U64_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataU64 * const me, uint64_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_UPDATED_WITHIN_US_AND_GET_TIMESTAMP_US_(me, pOutValue, durationUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U64_ReadIfIsNewForId(sSmartDataU64 * const me, uint64_t * pOutValue, eSmartDataUserId userId){

    READ_IF_IS_NEW_FOR_ID_(me, pOutValue, userId);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_U64_ReadIfIsNewForIdAndGetTimestamp(sSmartDataU64 * const me, uint64_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs){

    READ_IF_IS_NEW_FOR_ID_AND_GET_TIMESTAMP_US_(me, pOutValue, userId, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_U64_Write(sSmartDataU64 * const me, uint64_t *pValue){

    CHECK_RANGE_(me, pValue);
    WRITE_(me, pValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data of the parameter at an index of the
 *        parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a uint64_t.
 */
eSmartDataStatus fSmartData_U64_WriteByIndex(uint16_t index, uint64_t *pValue) {

    sSmartDataU64 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_U64, pSd);

    return fSmartData_U64_Write(pSd, pValue);
}

/**
 * @brief Writes a value to the smart data with the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @param timestampUs Timestamp associated with the value, in microseconds.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_U64_WriteWithTimestampUs(sSmartDataU64 * const me, uint64_t *pValue, uint64_t timestampUs){

    CHECK_RANGE_(me, pValue);
    WRITE_WITH_TIMESTAMP_US_(me, pValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Checks whether the smart data has been written at least once.
 *
 * @param me Pointer to the smart data object.
 * @return bool_t TRUE if the smart data has been written at least once, otherwise FALSE.
 */
bool_t fSmartData_U64_HasBeenWrittenSoFar(sSmartDataU64 * const me) {

    return HAS_BEEN_WRITTEN_SO_FAR_(me);
}

/**
 * @brief Verifies the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @return eSmartDataStatus Verification result.
 */
eSmartDataStatus fSmartData_U64_Verify(sSmartDataU64 * const me) {

    ASSERT_NOT_NULL_(me);
    CHECK_RANGE_(me, &(me->Value));

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U64_SetMinValue(sSmartDataU64 * const me, uint64_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MIN_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U64_GetMinValue(sSmartDataU64 * const me, uint64_t * pOutValue) {

    GET_MIN_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U64_SetMaxValue(sSmartDataU64 * const me, uint64_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MAX_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U64_GetMaxValue(sSmartDataU64 * const me, uint64_t * pOutValue) {

    GET_MAX_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U64_SetDefaultValue(sSmartDataU64 * const me, uint64_t * pNewValue) {

    CHECK_RANGE_(me, pNewValue);
    SET_DEFAULT_VALUE_(me, pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U64_GetDefaultValue(sSmartDataU64 * const me, uint64_t * pOutValue) {

    GET_DEFAULT_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U64_SetResolution(sSmartDataU64 * const me, uint64_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_RESOLUTION_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U64_GetResolution(sSmartDataU64 * const me, uint64_t * pOutValue) {

    GET_RESOLUTION_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the timestamp of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutTsUs Pointer to the output timestamp.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U64_GetTimestamp(sSmartDataU64 * const me, uint64_t * pOutTsUs) {

    GET_TIMESTAMP_(me, pOutTsUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U64_GetSmartDataSize(sSmartDataU64 * const me, size_t * pOutSize) {

    GET_SMART_DATA_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the value stored in the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_U64_GetValueSize(sSmartDataU64 * const me, size_t * pOutSize) {

    GET_VALUE_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                INT64_T                                   │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
/**
 * @brief Initializes a I64smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param minVal Minimum allowed value of the smart data.
 * @param maxVal Maximum allowed value of the smart data.
 * @param defaultVal Initial and default value of the smart data.
 * @param resolution Resolution of the smart data.
 * @param pUnit Pointer to the unit string of the smart data.
 * @return eSmartDataStatus Status of the initialization.
 */
eSmartDataStatus fSmartData_I64_Ctor(sSmartDataI64* const me, int64_t minVal, int64_t maxVal, int64_t defaultVal, int64_t resolution, const char *pUnit) {

    ASSERT_NOT_NULL_(me);
    ASSERT_DEFAULT_VALUE_(defaultVal, minVal, maxVal);

    me->_core.TypeInfo.Type = eSMART_DATA_TYPE_I64;
    me->_core.TypeInfo.ValueSize = sizeof(int64_t);
    me->_core.TypeInfo.SmartDataSize = sizeof(sSmartDataI64);

    me->_core.TimestampUs = 0x0ULL;
    me->_core.LastReadTimestampUs = 0x0ULL;

    me->_core.ReadWriteStatus.UserFlags = UINT32_MAX;
    me->_core.ReadWriteStatus.HasBeenWrittenOnce = FALSE;

    me->Value = defaultVal;
    me->_min = minVal;
    me->_max = maxVal;
    me->_defaultValue = defaultVal;
    me->_resolution = resolution;
    me->pUnit = (pUnit == NULL) ? "" : pUnit;

    return eSMART_DATA_OK;
}


/**
 * @brief Reads the current value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I64_Read(sSmartDataI64* const me, int64_t * pOutValue) {

    READ_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data of the parameter at an
 *        index of the parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a int64_t.
 */
eSmartDataStatus fSmartData_I64_ReadByIndex(uint16_t index, int64_t * pOutValue) {

    sSmartDataI64 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_I64, pSd);

    return fSmartData_I64_Read(pSd, pOutValue);
}

/**
 * @brief Reads the current value and its timestamp from the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I64_ReadAndGetTimestampUs(sSmartDataI64* const me, int64_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_AND_GET_TIMESTAMP_US_(me, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I64_ReadIfChanged(sSmartDataI64* const me, int64_t * pReferenceValue, int64_t * pOutValue)  {

    READ_IF_CHANGED_(me, pReferenceValue, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I64_ReadIfChangedAndGetTimestampUs(sSmartDataI64* const me, int64_t * pReferenceValue, int64_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_IF_CHANGED_AND_GET_TIMESTAMP_US_(me, pReferenceValue, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I64_ReadIfIsNewerThanTimestampUs(sSmartDataI64* const me, int64_t * pOutValue, uint64_t timestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_(me, pOutValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I64_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataI64* const me, int64_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_AND_GET_TIMESTAMP_US_(me, pOutValue, timestampUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I64_ReadIfIsUpdatedWithinUs(sSmartDataI64* const me, int64_t * pOutValue, uint64_t durationUs) {

    READ_IF_IS_UPDATED_WITHIN_US_(me, pOutValue, durationUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I64_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataI64* const me, int64_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_UPDATED_WITHIN_US_AND_GET_TIMESTAMP_US_(me, pOutValue, durationUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I64_ReadIfIsNewForId(sSmartDataI64* const me, int64_t * pOutValue, eSmartDataUserId userId){

    READ_IF_IS_NEW_FOR_ID_(me, pOutValue, userId);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_I64_ReadIfIsNewForIdAndGetTimestamp(sSmartDataI64* const me, int64_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs){

    READ_IF_IS_NEW_FOR_ID_AND_GET_TIMESTAMP_US_(me, pOutValue, userId, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_I64_Write(sSmartDataI64* const me, int64_t *pValue){

    CHECK_RANGE_(me, pValue);
    WRITE_(me, pValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data of the parameter at an index of the
 *        parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a int64_t.
 */
eSmartDataStatus fSmartData_I64_WriteByIndex(uint16_t index, int64_t *pValue) {

    sSmartDataI64 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_I64, pSd);

    return fSmartData_I64_Write(pSd, pValue);
}

/**
 * @brief Writes a value to the smart data with the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @param timestampUs Timestamp associated with the value, in microseconds.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_I64_WriteWithTimestampUs(sSmartDataI64* const me, int64_t *pValue, uint64_t timestampUs){

    CHECK_RANGE_(me, pValue);
    WRITE_WITH_TIMESTAMP_US_(me, pValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Checks whether the smart data has been written at least once.
 *
 * @param me Pointer to the smart data object.
 * @return bool_t TRUE if the smart data has been written at least once, otherwise FALSE.
 */
bool_t fSmartData_I64_HasBeenWrittenSoFar(sSmartDataI64* const me) {

    return HAS_BEEN_WRITTEN_SO_FAR_(me);
}

/**
 * @brief Verifies the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @return eSmartDataStatus Verification result.
 */
eSmartDataStatus fSmartData_I64_Verify(sSmartDataI64* const me) {

    ASSERT_NOT_NULL_(me);
    CHECK_RANGE_(me, &(me->Value));

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I64_SetMinValue(sSmartDataI64* const me, int64_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MIN_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I64_GetMinValue(sSmartDataI64* const me, int64_t * pOutValue) {

    GET_MIN_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I64_SetMaxValue(sSmartDataI64* const me, int64_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MAX_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I64_GetMaxValue(sSmartDataI64* const me, int64_t * pOutValue) {

    GET_MAX_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I64_SetDefaultValue(sSmartDataI64* const me, int64_t * pNewValue) {

    CHECK_RANGE_(me, pNewValue);
    SET_DEFAULT_VALUE_(me, pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I64_GetDefaultValue(sSmartDataI64* const me, int64_t * pOutValue) {

    GET_DEFAULT_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I64_SetResolution(sSmartDataI64* const me, int64_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_RESOLUTION_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I64_GetResolution(sSmartDataI64* const me, int64_t * pOutValue) {

    GET_RESOLUTION_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the timestamp of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutTsUs Pointer to the output timestamp.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I64_GetTimestamp(sSmartDataI64* const me, uint64_t * pOutTsUs) {

    GET_TIMESTAMP_(me, pOutTsUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I64_GetSmartDataSize(sSmartDataI64* const me, size_t * pOutSize) {

    GET_SMART_DATA_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the value stored in the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_I64_GetValueSize(sSmartDataI64* const me, size_t * pOutSize) {

    GET_VALUE_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                               FLOAT32_T                                  │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
/**
 * @brief Initializes a F32smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param minVal Minimum allowed value of the smart data.
 * @param maxVal Maximum allowed value of the smart data.
 * @param defaultVal Initial and default value of the smart data.
 * @param resolution Resolution of the smart data.
 * @param pUnit Pointer to the unit string of the smart data.
 * @return eSmartDataStatus Status of the initialization.
 */
eSmartDataStatus fSmartData_F32_Ctor(sSmartDataF32* const me, float32_t minVal, float32_t maxVal, float32_t defaultVal, float32_t resolution, const char *pUnit) {

    ASSERT_NOT_NULL_(me);
    ASSERT_DEFAULT_VALUE_(defaultVal, minVal, maxVal);

    me->_core.TypeInfo.Type = eSMART_DATA_TYPE_F32;
    me->_core.TypeInfo.ValueSize = sizeof(float32_t);
    me->_core.TypeInfo.SmartDataSize = sizeof(sSmartDataF32);

    me->_core.TimestampUs = 0x0ULL;
    me->_core.LastReadTimestampUs = 0x0ULL;

    me->_core.ReadWriteStatus.UserFlags = UINT32_MAX;
    me->_core.ReadWriteStatus.HasBeenWrittenOnce = FALSE;

    me->Value = defaultVal;
    me->_min = minVal;
    me->_max = maxVal;
    me->_defaultValue = defaultVal;
    me->_resolution = resolution;
    me->pUnit = (pUnit == NULL) ? "" : pUnit;

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F32_Read(sSmartDataF32* const me, float32_t * pOutValue) {

    READ_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data of the parameter at an
 *        index of the parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a float32_t.
 */
eSmartDataStatus fSmartData_F32_ReadByIndex(uint16_t index, float32_t * pOutValue) {

    sSmartDataF32 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_F32, pSd);

    return fSmartData_F32_Read(pSd, pOutValue);
}

/**
 * @brief Reads the current value and its timestamp from the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F32_ReadAndGetTimestampUs(sSmartDataF32* const me, float32_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_AND_GET_TIMESTAMP_US_(me, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F32_ReadIfChanged(sSmartDataF32* const me, float32_t * pReferenceValue, float32_t * pOutValue)  {

    READ_IF_CHANGED_(me, pReferenceValue, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F32_ReadIfChangedAndGetTimestampUs(sSmartDataF32* const me, float32_t * pReferenceValue, float32_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_IF_CHANGED_AND_GET_TIMESTAMP_US_(me, pReferenceValue, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F32_ReadIfIsNewerThanTimestampUs(sSmartDataF32* const me, float32_t * pOutValue, uint64_t timestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_(me, pOutValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F32_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataF32* const me, float32_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_AND_GET_TIMESTAMP_US_(me, pOutValue, timestampUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F32_ReadIfIsUpdatedWithinUs(sSmartDataF32* const me, float32_t * pOutValue, uint64_t durationUs) {

    READ_IF_IS_UPDATED_WITHIN_US_(me, pOutValue, durationUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F32_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataF32* const me, float32_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_UPDATED_WITHIN_US_AND_GET_TIMESTAMP_US_(me, pOutValue, durationUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F32_ReadIfIsNewForId(sSmartDataF32* const me, float32_t * pOutValue, eSmartDataUserId userId){

    READ_IF_IS_NEW_FOR_ID_(me, pOutValue, userId);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F32_ReadIfIsNewForIdAndGetTimestamp(sSmartDataF32* const me, float32_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs){

    READ_IF_IS_NEW_FOR_ID_AND_GET_TIMESTAMP_US_(me, pOutValue, userId, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_F32_Write(sSmartDataF32* const me, float32_t *pValue){

    CHECK_RANGE_(me, pValue);
    WRITE_(me, pValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data of the parameter at an index of the
 *        parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a float32_t.
 */
eSmartDataStatus fSmartData_F32_WriteByIndex(uint16_t index, float32_t *pValue) {

    sSmartDataF32 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_F32, pSd);

    return fSmartData_F32_Write(pSd, pValue);
}

/**
 * @brief Writes a value to the smart data with the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @param timestampUs Timestamp associated with the value, in microseconds.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_F32_WriteWithTimestampUs(sSmartDataF32* const me, float32_t *pValue, uint64_t timestampUs){

    CHECK_RANGE_(me, pValue);
    WRITE_WITH_TIMESTAMP_US_(me, pValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Checks whether the smart data has been written at least once.
 *
 * @param me Pointer to the smart data object.
 * @return bool_t TRUE if the smart data has been written at least once, otherwise FALSE.
 */
bool_t fSmartData_F32_HasBeenWrittenSoFar(sSmartDataF32* const me) {

    return HAS_BEEN_WRITTEN_SO_FAR_(me);
}

/**
 * @brief Verifies the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @return eSmartDataStatus Verification result.
 */
eSmartDataStatus fSmartData_F32_Verify(sSmartDataF32* const me) {

    ASSERT_NOT_NULL_(me);
    CHECK_RANGE_(me, &(me->Value));

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F32_SetMinValue(sSmartDataF32* const me, float32_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MIN_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F32_GetMinValue(sSmartDataF32* const me, float32_t * pOutValue) {

    GET_MIN_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F32_SetMaxValue(sSmartDataF32* const me, float32_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MAX_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F32_GetMaxValue(sSmartDataF32* const me, float32_t * pOutValue) {

    GET_MAX_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F32_SetDefaultValue(sSmartDataF32* const me, float32_t * pNewValue) {

    CHECK_RANGE_(me, pNewValue);
    SET_DEFAULT_VALUE_(me, pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F32_GetDefaultValue(sSmartDataF32* const me, float32_t * pOutValue) {

    GET_DEFAULT_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F32_SetResolution(sSmartDataF32* const me, float32_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_RESOLUTION_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F32_GetResolution(sSmartDataF32* const me, float32_t * pOutValue) {

    GET_RESOLUTION_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the timestamp of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutTsUs Pointer to the output timestamp.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F32_GetTimestamp(sSmartDataF32* const me, uint64_t * pOutTsUs) {

    GET_TIMESTAMP_(me, pOutTsUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F32_GetSmartDataSize(sSmartDataF32* const me, size_t * pOutSize) {

    GET_SMART_DATA_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the value stored in the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F32_GetValueSize(sSmartDataF32* const me, size_t * pOutSize) {

    GET_VALUE_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                               FLOAT64_T                                  │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
/**
 * @brief Initializes a F64 smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param minVal Minimum allowed value of the smart data.
 * @param maxVal Maximum allowed value of the smart data.
 * @param defaultVal Initial and default value of the smart data.
 * @param resolution Resolution of the smart data.
 * @param pUnit Pointer to the unit string of the smart data.
 * @return eSmartDataStatus Status of the initialization.
 */
eSmartDataStatus fSmartData_F64_Ctor(sSmartDataF64 * const me, float64_t minVal, float64_t maxVal, float64_t defaultVal, float64_t resolution, const char *pUnit) {

    ASSERT_NOT_NULL_(me);
    ASSERT_DEFAULT_VALUE_(defaultVal, minVal, maxVal);

    me->_core.TypeInfo.Type = eSMART_DATA_TYPE_F64;
    me->_core.TypeInfo.ValueSize = sizeof(float64_t);
    me->_core.TypeInfo.SmartDataSize = sizeof(sSmartDataF64);

    me->_core.TimestampUs = 0x0ULL;
    me->_core.LastReadTimestampUs = 0x0ULL;

    me->_core.ReadWriteStatus.UserFlags = UINT32_MAX;
    me->_core.ReadWriteStatus.HasBeenWrittenOnce = FALSE;

    me->Value = defaultVal;
    me->_min = minVal;
    me->_max = maxVal;
    me->_defaultValue = defaultVal;
    me->_resolution = resolution;
    me->pUnit = (pUnit == NULL) ? "" : pUnit;

    return eSMART_DATA_OK;
}


/**
 * @brief Reads the current value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F64_Read(sSmartDataF64 * const me, float64_t * pOutValue) {

    READ_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the current value of the smart data of the parameter at an
 *        index of the parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a float64_t.
 */
eSmartDataStatus fSmartData_F64_ReadByIndex(uint16_t index, float64_t * pOutValue) {

    sSmartDataF64 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_F64, pSd);

    return fSmartData_F64_Read(pSd, pOutValue);
}

/**
 * @brief Reads the current value and its timestamp from the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F64_ReadAndGetTimestampUs(sSmartDataF64 * const me, float64_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_AND_GET_TIMESTAMP_US_(me, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F64_ReadIfChanged(sSmartDataF64 * const me, float64_t * pReferenceValue, float64_t * pOutValue)  {

    READ_IF_CHANGED_(me, pReferenceValue, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its value differs from a reference value.
 *
 * @param me Pointer to the smart data object.
 * @param pReferenceValue Pointer to the value to compare with - typically the one
 *        the caller read last.
 * @param pOutValue Pointer to the output value.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F64_ReadIfChangedAndGetTimestampUs(sSmartDataF64 * const me, float64_t * pReferenceValue, float64_t * pOutValue, uint64_t *pOutTimestampUs) {

    READ_IF_CHANGED_AND_GET_TIMESTAMP_US_(me, pReferenceValue, pOutValue, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F64_ReadIfIsNewerThanTimestampUs(sSmartDataF64 * const me, float64_t * pOutValue, uint64_t timestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_(me, pOutValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if its timestamp is newer than the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param timestampUs Reference timestamp in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F64_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataF64 * const me, float64_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_NEWER_THAN_TIMESTAMP_US_AND_GET_TIMESTAMP_US_(me, pOutValue, timestampUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F64_ReadIfIsUpdatedWithinUs(sSmartDataF64 * const me, float64_t * pOutValue, uint64_t durationUs) {

    READ_IF_IS_UPDATED_WITHIN_US_(me, pOutValue, durationUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if it has been updated within the specified duration.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param durationUs Maximum allowed time since the last update, in microseconds.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F64_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataF64 * const me, float64_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs) {

    READ_IF_IS_UPDATED_WITHIN_US_AND_GET_TIMESTAMP_US_(me, pOutValue, durationUs, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F64_ReadIfIsNewForId(sSmartDataF64 * const me, float64_t * pOutValue, eSmartDataUserId userId){

    READ_IF_IS_NEW_FOR_ID_(me, pOutValue, userId);

    return eSMART_DATA_OK;
}

/**
 * @brief Reads the smart data and its timestamp only if new data is available for the specified user.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output value.
 * @param userId Identifier of the user requesting the data.
 * @param pOutTimestampUs Pointer to the output timestamp in microseconds.
 * @return eSmartDataStatus Status of the read operation.
 */
eSmartDataStatus fSmartData_F64_ReadIfIsNewForIdAndGetTimestamp(sSmartDataF64 * const me, float64_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs){

    READ_IF_IS_NEW_FOR_ID_AND_GET_TIMESTAMP_US_(me, pOutValue, userId, pOutTimestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_F64_Write(sSmartDataF64 * const me, float64_t *pValue){

    CHECK_RANGE_(me, pValue);
    WRITE_(me, pValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Writes a value to the smart data of the parameter at an index of the
 *        parameter list.
 *
 * @param index Index of the parameter in the parameter list.
 * @param pValue Pointer to the value to be written.
 * @return eSmartDataStatus Status of the write operation;
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED if that parameter is not
 *         a float64_t.
 */
eSmartDataStatus fSmartData_F64_WriteByIndex(uint16_t index, float64_t *pValue) {

    sSmartDataF64 *pSd = NULL;

    GET_BY_INDEX_(index, eSMART_DATA_TYPE_F64, pSd);

    return fSmartData_F64_Write(pSd, pValue);
}

/**
 * @brief Writes a value to the smart data with the specified timestamp.
 *
 * @param me Pointer to the smart data object.
 * @param pValue Pointer to the value to be written.
 * @param timestampUs Timestamp associated with the value, in microseconds.
 * @return eSmartDataStatus Status of the write operation.
 */
eSmartDataStatus fSmartData_F64_WriteWithTimestampUs(sSmartDataF64 * const me, float64_t *pValue, uint64_t timestampUs){

    CHECK_RANGE_(me, pValue);
    WRITE_WITH_TIMESTAMP_US_(me, pValue, timestampUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Checks whether the smart data has been written at least once.
 *
 * @param me Pointer to the smart data object.
 * @return bool_t TRUE if the smart data has been written at least once, otherwise FALSE.
 */
bool_t fSmartData_F64_HasBeenWrittenSoFar(sSmartDataF64 * const me) {

    return HAS_BEEN_WRITTEN_SO_FAR_(me);
}

/**
 * @brief Verifies the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @return eSmartDataStatus Verification result.
 */
eSmartDataStatus fSmartData_F64_Verify(sSmartDataF64 * const me) {

    ASSERT_NOT_NULL_(me);
    CHECK_RANGE_(me, &(me->Value));

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F64_SetMinValue(sSmartDataF64 * const me, float64_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MIN_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the minimum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output minimum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F64_GetMinValue(sSmartDataF64 * const me, float64_t * pOutValue) {

    GET_MIN_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F64_SetMaxValue(sSmartDataF64 * const me, float64_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_MAX_VALUE_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the maximum value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output maximum value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F64_GetMaxValue(sSmartDataF64 * const me, float64_t * pOutValue) {

    GET_MAX_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F64_SetDefaultValue(sSmartDataF64 * const me, float64_t * pNewValue) {

    CHECK_RANGE_(me, pNewValue);
    SET_DEFAULT_VALUE_(me, pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the default value of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output default value.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F64_GetDefaultValue(sSmartDataF64 * const me, float64_t * pOutValue) {

    GET_DEFAULT_VALUE_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Sets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pNewValue Pointer to the new resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F64_SetResolution(sSmartDataF64 * const me, float64_t * pNewValue) {

    ASSERT_NOT_NULL_(me);
    ASSERT_NOT_NULL_(pNewValue);

    SET_RESOLUTION_(me, *pNewValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the resolution of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutValue Pointer to the output resolution.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F64_GetResolution(sSmartDataF64 * const me, float64_t * pOutValue) {

    GET_RESOLUTION_(me, pOutValue);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the timestamp of the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutTsUs Pointer to the output timestamp.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F64_GetTimestamp(sSmartDataF64 * const me, uint64_t * pOutTsUs) {

    GET_TIMESTAMP_(me, pOutTsUs);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the smart data object.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F64_GetSmartDataSize(sSmartDataF64 * const me, size_t * pOutSize) {

    GET_SMART_DATA_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/**
 * @brief Gets the size of the value stored in the smart data.
 *
 * @param me Pointer to the smart data object.
 * @param pOutSize Pointer to the output size.
 * @return eSmartDataStatus Status of operation.
 */
eSmartDataStatus fSmartData_F64_GetValueSize(sSmartDataF64 * const me, size_t * pOutSize) {

    GET_VALUE_SIZE_(me, pOutSize);

    return eSMART_DATA_OK;
}

/*
  ==============================================================================
                        ##### Private Functions #####
  ==============================================================================
*/

/* === Copyright (c) 2026 FAS === EOF === */
