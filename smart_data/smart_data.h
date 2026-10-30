/**
  ******************************************************************************
  * @file    smart_data.h
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
  */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef SMART_DATA_H
#define SMART_DATA_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ----------------------------------------------------------------- */
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

/* Exported defines --------------------------------------------------------- */
#ifndef float32_t__

#define float32_t__
typedef float   float32_t;

#endif  //float32_t__

#ifndef float64_t__

#define float64_t__
typedef double  float64_t;

#endif  //float64_t__

#ifndef bool_t__

#define bool_t__

typedef bool    bool_t;

#ifndef FALSE
#define FALSE ((bool_t)0)
#endif  //FALSE

#ifndef TRUE
#define TRUE  ((bool_t)1)
#endif  //TRUE

#endif  //bool_t__

/* Exported macros ---------------------------------------------------------- */

/* Exported types ----------------------------------------------------------- */
/**
 * @brief
 *
 */
typedef enum {

    eSMART_DATA_OK = 0,
    eSMART_DATA_ERROR_NULL_POINTER,
    eSMART_DATA_ERROR_DEFAULT_VALUE_OUT_OF_RANGE,
    eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE,
    eSMART_DATA_ERROR_NOT_APPLICABLE,
    eSMART_DATA_ERROR_INVALID_USER_NUMBER,
    eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED,
    eSMART_DATA_ERROR_NO_NEW_DATA,
    eSMART_DATA_ERROR_DATA_NOT_CHANGED,

} eSmartDataStatus;

/**
 * @brief
 *
 */
typedef enum {

    eSMART_DATA_TYPE_B8 = 0,
    eSMART_DATA_TYPE_U8,
    eSMART_DATA_TYPE_I8,
    eSMART_DATA_TYPE_U16,
    eSMART_DATA_TYPE_I16,
    eSMART_DATA_TYPE_U32,
    eSMART_DATA_TYPE_I32,
    eSMART_DATA_TYPE_U64,
    eSMART_DATA_TYPE_I64,
    eSMART_DATA_TYPE_F32,
    eSMART_DATA_TYPE_F64,
    eSMART_DATA_TYPE_ENUMERATION

} eSmartDataType;

/**
 * @brief
 *
 */
typedef enum {

    eSMART_DATA_USER_ID_1 = 0,
    eSMART_DATA_USER_ID_2,
    eSMART_DATA_USER_ID_3,
    eSMART_DATA_USER_ID_4,
    eSMART_DATA_USER_ID_5,
    eSMART_DATA_USER_ID_6,
    eSMART_DATA_USER_ID_7,
    eSMART_DATA_USER_ID_8,
    eSMART_DATA_USER_ID_9,
    eSMART_DATA_USER_ID_10,
    eSMART_DATA_USER_ID_11,
    eSMART_DATA_USER_ID_12,
    eSMART_DATA_USER_ID_13,
    eSMART_DATA_USER_ID_14,
    eSMART_DATA_USER_ID_15,
    eSMART_DATA_USER_ID_16,
    eSMART_DATA_USER_ID_17,
    eSMART_DATA_USER_ID_18,
    eSMART_DATA_USER_ID_19,
    eSMART_DATA_USER_ID_20,
    eSMART_DATA_USER_ID_21,
    eSMART_DATA_USER_ID_22,
    eSMART_DATA_USER_ID_23,
    eSMART_DATA_USER_ID_24,
    eSMART_DATA_USER_ID_25,
    eSMART_DATA_USER_ID_26,
    eSMART_DATA_USER_ID_27,
    eSMART_DATA_USER_ID_28,
    eSMART_DATA_USER_ID_29,
    eSMART_DATA_USER_ID_30,
    eSMART_DATA_USER_ID_31,
    eSMART_DATA_USER_ID_32,

    eSMART_DATA_USER_ID_QTY

} eSmartDataUserId;

/**
 * @brief
 *
 */
typedef struct {

    eSmartDataType Type;

    size_t SmartDataSize;

    size_t ValueSize;

} sSmartDataTypeInfo;

/**
 * @brief
 *
 */
/**
 * @brief Decides whether a value is one a smart data object may hold.
 *
 * Set on the object of an enumeration (see fSmartData_SetIsValid): every write
 * then refuses a value this answers FALSE for, even one inside the range.
 *
 * @param pValue The value, of the object's own type.
 * @return bool_t TRUE when the value is allowed.
 */
typedef bool_t (*fSmartDataIsValid)(const void *pValue);

/**
 * @brief
 *
 */
typedef struct {

    sSmartDataTypeInfo TypeInfo;

    fSmartDataIsValid pIsValid;     /*!< NULL, or which values the object may hold (an enumeration). In the 32-bit padding gap: no extra RAM. */

    uint64_t TimestampUs;

    uint64_t LastReadTimestampUs;

    struct {

        uint32_t UserFlags;

        bool_t HasBeenWrittenOnce;

    } ReadWriteStatus;

} sSmartDataCore;

/**
 * @brief
 *
 */
typedef struct {

    sSmartDataCore _core;           /*!< Smart data core info. This must be the first element in the smart data structures! */

    bool_t Value;                   /*!< Value of the smart data. */

    bool_t _defaultValue;           /*!< Default value of the smart data. */

} sSmartDataB8;

/**
 * @brief
 *
 */
typedef struct {

    sSmartDataCore _core;       /*!< Smart data core info. This must be the first element in the smart data structures! */

    uint8_t Value;              /*!< Value of the smart data. */

    uint8_t _min;               /*!< Minimum value in the range of the smart data. */

    uint8_t _max;               /*!< Maximum value in the range of the smart data. */

    uint8_t _defaultValue;      /*!< Default value of the smart data. */

    uint8_t _resolution;        /*!< Resolution of the smart data. */

    const char *pUnit;                /*!< Unit string of the instantiated smart data. */

} sSmartDataU8;

/**
 * @brief
 *
 */
typedef struct {

    sSmartDataCore _core;       /*!< Smart data core info. This must be the first element in the smart data structures! */

    int8_t Value;               /*!< Value of the smart data. */

    int8_t _min;                /*!< Minimum value in the range of the smart data. */

    int8_t _max;                /*!< Maximum value in the range of the smart data. */

    int8_t _defaultValue;       /*!< Default value of the smart data. */

    int8_t _resolution;         /*!< Resolution of the smart data. */

    const char *pUnit;                /*!< Unit string of the instantiated smart data. */

} sSmartDataI8;

/**
 * @brief
 *
 */
typedef struct {

    sSmartDataCore _core;       /*!< Smart data core info. This must be the first element in the smart data structures! */

    uint16_t Value;             /*!< Value of the smart data. */

    uint16_t _min;              /*!< Minimum value in the range of the smart data. */

    uint16_t _max;              /*!< Maximum value in the range of the smart data. */

    uint16_t _defaultValue;     /*!< Default value of the smart data. */

    uint16_t _resolution;       /*!< Resolution of the smart data. */

    const char *pUnit;                /*!< Unit string of the instantiated smart data. */

} sSmartDataU16;

/**
 * @brief
 *
 */
typedef struct {

    sSmartDataCore _core;       /*!< Smart data core info. This must be the first element in the smart data structures! */

    int16_t Value;              /*!< Value of the smart data. */

    int16_t _min;               /*!< Minimum value in the range of the smart data. */

    int16_t _max;               /*!< Maximum value in the range of the smart data. */

    int16_t _defaultValue;      /*!< Default value of the smart data. */

    int16_t _resolution;        /*!< Resolution of the smart data. */

    const char *pUnit;                /*!< Unit string of the instantiated smart data. */

} sSmartDataI16;

/**
 * @brief
 *
 */
typedef struct {

    sSmartDataCore _core;       /*!< Smart data core info. This must be the first element in the smart data structures! */

    uint32_t Value;             /*!< Value of the smart data. */

    uint32_t _min;              /*!< Minimum value in the range of the smart data. */

    uint32_t _max;              /*!< Maximum value in the range of the smart data. */

    uint32_t _defaultValue;     /*!< Default value of the smart data. */

    uint32_t _resolution;       /*!< Resolution of the smart data. */

    const char *pUnit;                /*!< Unit string of the instantiated smart data. */

} sSmartDataU32;

/**
 * @brief
 *
 */
typedef struct {

    sSmartDataCore _core;       /*!< Smart data core info. This must be the first element in the smart data structures! */

    int32_t Value;              /*!< Value of the smart data. */

    int32_t _min;               /*!< Minimum value in the range of the smart data. */

    int32_t _max;               /*!< Maximum value in the range of the smart data. */

    int32_t _defaultValue;      /*!< Default value of the smart data. */

    int32_t _resolution;        /*!< Resolution of the smart data. */

    const char *pUnit;                /*!< Unit string of the instantiated smart data. */

} sSmartDataI32;

/**
 * @brief
 *
 */
typedef struct {

    sSmartDataCore _core;       /*!< Smart data core info. This must be the first element in the smart data structures! */

    uint64_t Value;             /*!< Value of the smart data. */

    uint64_t _min;              /*!< Minimum value in the range of the smart data. */

    uint64_t _max;              /*!< Maximum value in the range of the smart data. */

    uint64_t _defaultValue;     /*!< Default value of the smart data. */

    uint64_t _resolution;       /*!< Resolution of the smart data. */

    const char *pUnit;                /*!< Unit string of the instantiated smart data. */

} sSmartDataU64;

/**
 * @brief
 *
 */
typedef struct {

    sSmartDataCore _core;       /*!< Smart data core info. This must be the first element in the smart data structures! */

    int64_t Value;              /*!< Value of the smart data. */

    int64_t _min;               /*!< Minimum value in the range of the smart data. */

    int64_t _max;               /*!< Maximum value in the range of the smart data. */

    int64_t _defaultValue;      /*!< Default value of the smart data. */

    int64_t _resolution;        /*!< Resolution of the smart data. */

    const char *pUnit;                /*!< Unit string of the instantiated smart data. */

} sSmartDataI64;

/**
 * @brief
 *
 */
typedef struct {

    sSmartDataCore _core;       /*!< Smart data core info. This must be the first element in the smart data structures! */

    float32_t Value;            /*!< Value of the smart data. */

    float32_t _min;             /*!< Minimum value in the range of the smart data. */

    float32_t _max;             /*!< Maximum value in the range of the smart data. */

    float32_t _defaultValue;    /*!< Default value of the smart data. */

    float32_t _resolution;      /*!< Resolution of the smart data. */

    const char *pUnit;                /*!< Unit string of the instantiated smart data. */

} sSmartDataF32;

/**
 * @brief
 *
 */
typedef struct {

    sSmartDataCore _core;       /*!< Smart data core info. This must be the first element in the smart data structures! */

    float64_t Value;            /*!< Value of the smart data. */

    float64_t _min;             /*!< Minimum value in the range of the smart data. */

    float64_t _max;             /*!< Maximum value in the range of the smart data. */

    float64_t _defaultValue;    /*!< Default value of the smart data. */

    float64_t _resolution;      /*!< Resolution of the smart data. */

    const char *pUnit;                /*!< Unit string of the instantiated smart data. */

} sSmartDataF64;

/* Exported functions ------------------------------------------------------- */

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                BOOLEAN                                   │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
eSmartDataStatus fSmartData_B8_Ctor(sSmartDataB8 * const me, bool_t defaultVal);
eSmartDataStatus fSmartData_B8_Read(sSmartDataB8 * const me, bool_t * pOutValue);
eSmartDataStatus fSmartData_B8_ReadByIndex(uint16_t index, bool_t * pOutValue);
eSmartDataStatus fSmartData_B8_ReadAndGetTimestampUs(sSmartDataB8 * const me, bool_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_B8_ReadIfChanged(sSmartDataB8 * const me, bool_t * pReferenceValue, bool_t * pOutValue);
eSmartDataStatus fSmartData_B8_ReadIfChangedAndGetTimestampUs(sSmartDataB8 * const me, bool_t * pReferenceValue, bool_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_B8_ReadIfIsNewerThanTimestampUs(sSmartDataB8 * const me, bool_t * pOutValue, uint64_t timestampUs);
eSmartDataStatus fSmartData_B8_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataB8 * const me, bool_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_B8_ReadIfIsUpdatedWithinUs(sSmartDataB8 * const me, bool_t * pOutValue, uint64_t durationUs);
eSmartDataStatus fSmartData_B8_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataB8 * const me, bool_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_B8_ReadIfIsNewForId(sSmartDataB8 * const me, bool_t * pOutValue, eSmartDataUserId userId);
eSmartDataStatus fSmartData_B8_ReadIfIsNewForIdAndGetTimestamp(sSmartDataB8 * const me, bool_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_B8_Write(sSmartDataB8 * const me, bool_t *pValue);
eSmartDataStatus fSmartData_B8_WriteByIndex(uint16_t index, bool_t *pValue);
eSmartDataStatus fSmartData_B8_WriteWithTimestampUs(sSmartDataB8 * const me, bool_t *pValue, uint64_t timestampUs);
bool_t fSmartData_B8_HasBeenWrittenSoFar(sSmartDataB8 * const me);
eSmartDataStatus fSmartData_B8_SetDefaultValue(sSmartDataB8 * const me, bool_t * pNewValue);
eSmartDataStatus fSmartData_B8_GetDefaultValue(sSmartDataB8 * const me, bool_t * pOutValue);
eSmartDataStatus fSmartData_B8_GetTimestamp(sSmartDataB8 * const me, uint64_t *pOutTsUs);
eSmartDataStatus fSmartData_B8_GetSmartDataSize(sSmartDataB8 * const me, size_t *pOutSize);
eSmartDataStatus fSmartData_B8_GetValueSize(sSmartDataB8 * const me, size_t *pOutSize);

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                UINT8_T                                   │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
eSmartDataStatus fSmartData_U8_Ctor(sSmartDataU8 * const me, uint8_t minVal, uint8_t maxVal, uint8_t defaultVal, uint8_t resolution, const char *pUnit);
eSmartDataStatus fSmartData_U8_Read(sSmartDataU8 * const me, uint8_t * pOutValue);
eSmartDataStatus fSmartData_U8_ReadByIndex(uint16_t index, uint8_t * pOutValue);
eSmartDataStatus fSmartData_U8_ReadAndGetTimestampUs(sSmartDataU8 * const me, uint8_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U8_ReadIfChanged(sSmartDataU8 * const me, uint8_t * pReferenceValue, uint8_t * pOutValue);
eSmartDataStatus fSmartData_U8_ReadIfChangedAndGetTimestampUs(sSmartDataU8 * const me, uint8_t * pReferenceValue, uint8_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U8_ReadIfIsNewerThanTimestampUs(sSmartDataU8 * const me, uint8_t * pOutValue, uint64_t timestampUs);
eSmartDataStatus fSmartData_U8_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataU8 * const me, uint8_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U8_ReadIfIsUpdatedWithinUs(sSmartDataU8 * const me, uint8_t * pOutValue, uint64_t durationUs);
eSmartDataStatus fSmartData_U8_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataU8 * const me, uint8_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U8_ReadIfIsNewForId(sSmartDataU8 * const me, uint8_t * pOutValue, eSmartDataUserId userId);
eSmartDataStatus fSmartData_U8_ReadIfIsNewForIdAndGetTimestamp(sSmartDataU8 * const me, uint8_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U8_Write(sSmartDataU8 * const me, uint8_t *pValue);
eSmartDataStatus fSmartData_U8_WriteByIndex(uint16_t index, uint8_t *pValue);
eSmartDataStatus fSmartData_U8_WriteWithTimestampUs(sSmartDataU8 * const me, uint8_t *pValue, uint64_t timestampUs);
bool_t fSmartData_U8_HasBeenWrittenSoFar(sSmartDataU8 * const me);
eSmartDataStatus fSmartData_U8_Verify(sSmartDataU8 * const me);
eSmartDataStatus fSmartData_U8_SetMinValue(sSmartDataU8 * const me, uint8_t * pNewValue);
eSmartDataStatus fSmartData_U8_GetMinValue(sSmartDataU8 * const me, uint8_t * pOutValue);
eSmartDataStatus fSmartData_U8_SetMaxValue(sSmartDataU8 * const me, uint8_t * pNewValue);
eSmartDataStatus fSmartData_U8_GetMaxValue(sSmartDataU8 * const me, uint8_t * pOutValue);
eSmartDataStatus fSmartData_U8_SetDefaultValue(sSmartDataU8 * const me, uint8_t * pNewValue);
eSmartDataStatus fSmartData_U8_GetDefaultValue(sSmartDataU8 * const me, uint8_t * pOutValue);
eSmartDataStatus fSmartData_U8_SetResolution(sSmartDataU8 * const me, uint8_t * pNewValue);
eSmartDataStatus fSmartData_U8_GetResolution(sSmartDataU8 * const me, uint8_t * pOutValue);
eSmartDataStatus fSmartData_U8_GetTimestamp(sSmartDataU8 * const me, uint64_t *pOutTsUs);
eSmartDataStatus fSmartData_U8_GetSmartDataSize(sSmartDataU8 * const me, size_t *pOutSize);
eSmartDataStatus fSmartData_U8_GetValueSize(sSmartDataU8 * const me, size_t *pOutSize);

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                INT8_T                                    │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
eSmartDataStatus fSmartData_I8_Ctor(sSmartDataI8 * const me, int8_t minVal, int8_t maxVal, int8_t defaultVal, int8_t resolution, const char *pUnit);
eSmartDataStatus fSmartData_I8_Read(sSmartDataI8 * const me, int8_t * pOutValue);
eSmartDataStatus fSmartData_I8_ReadByIndex(uint16_t index, int8_t * pOutValue);
eSmartDataStatus fSmartData_I8_ReadAndGetTimestampUs(sSmartDataI8 * const me, int8_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I8_ReadIfChanged(sSmartDataI8 * const me, int8_t * pReferenceValue, int8_t * pOutValue);
eSmartDataStatus fSmartData_I8_ReadIfChangedAndGetTimestampUs(sSmartDataI8 * const me, int8_t * pReferenceValue, int8_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I8_ReadIfIsNewerThanTimestampUs(sSmartDataI8 * const me, int8_t * pOutValue, uint64_t timestampUs);
eSmartDataStatus fSmartData_I8_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataI8 * const me, int8_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I8_ReadIfIsUpdatedWithinUs(sSmartDataI8 * const me, int8_t * pOutValue, uint64_t durationUs);
eSmartDataStatus fSmartData_I8_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataI8 * const me, int8_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I8_ReadIfIsNewForId(sSmartDataI8 * const me, int8_t * pOutValue, eSmartDataUserId userId);
eSmartDataStatus fSmartData_I8_ReadIfIsNewForIdAndGetTimestamp(sSmartDataI8 * const me, int8_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I8_Write(sSmartDataI8 * const me, int8_t *pValue);
eSmartDataStatus fSmartData_I8_WriteByIndex(uint16_t index, int8_t *pValue);
eSmartDataStatus fSmartData_I8_WriteWithTimestampUs(sSmartDataI8 * const me, int8_t *pValue, uint64_t timestampUs);
bool_t fSmartData_I8_HasBeenWrittenSoFar(sSmartDataI8 * const me);
eSmartDataStatus fSmartData_I8_Verify(sSmartDataI8 * const me);
eSmartDataStatus fSmartData_I8_SetMinValue(sSmartDataI8 * const me, int8_t * pNewValue);
eSmartDataStatus fSmartData_I8_GetMinValue(sSmartDataI8 * const me, int8_t * pOutValue);
eSmartDataStatus fSmartData_I8_SetMaxValue(sSmartDataI8 * const me, int8_t * pNewValue);
eSmartDataStatus fSmartData_I8_GetMaxValue(sSmartDataI8 * const me, int8_t * pOutValue);
eSmartDataStatus fSmartData_I8_SetDefaultValue(sSmartDataI8 * const me, int8_t * pNewValue);
eSmartDataStatus fSmartData_I8_GetDefaultValue(sSmartDataI8 * const me, int8_t * pOutValue);
eSmartDataStatus fSmartData_I8_SetResolution(sSmartDataI8 * const me, int8_t * pNewValue);
eSmartDataStatus fSmartData_I8_GetResolution(sSmartDataI8 * const me, int8_t * pOutValue);
eSmartDataStatus fSmartData_I8_GetTimestamp(sSmartDataI8 * const me, uint64_t *pOutTsUs);
eSmartDataStatus fSmartData_I8_GetSmartDataSize(sSmartDataI8 * const me, size_t *pOutSize);
eSmartDataStatus fSmartData_I8_GetValueSize(sSmartDataI8 * const me, size_t *pOutSize);

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                UINT16_T                                  │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
eSmartDataStatus fSmartData_U16_Ctor(sSmartDataU16 * const me, uint16_t minVal, uint16_t maxVal, uint16_t defaultVal, uint16_t resolution, const char *pUnit);
eSmartDataStatus fSmartData_U16_Read(sSmartDataU16 * const me, uint16_t * pOutValue);
eSmartDataStatus fSmartData_U16_ReadByIndex(uint16_t index, uint16_t * pOutValue);
eSmartDataStatus fSmartData_U16_ReadAndGetTimestampUs(sSmartDataU16 * const me, uint16_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U16_ReadIfChanged(sSmartDataU16 * const me, uint16_t * pReferenceValue, uint16_t * pOutValue);
eSmartDataStatus fSmartData_U16_ReadIfChangedAndGetTimestampUs(sSmartDataU16 * const me, uint16_t * pReferenceValue, uint16_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U16_ReadIfIsNewerThanTimestampUs(sSmartDataU16 * const me, uint16_t * pOutValue, uint64_t timestampUs);
eSmartDataStatus fSmartData_U16_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataU16 * const me, uint16_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U16_ReadIfIsUpdatedWithinUs(sSmartDataU16 * const me, uint16_t * pOutValue, uint64_t durationUs);
eSmartDataStatus fSmartData_U16_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataU16 * const me, uint16_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U16_ReadIfIsNewForId(sSmartDataU16 * const me, uint16_t * pOutValue, eSmartDataUserId userId);
eSmartDataStatus fSmartData_U16_ReadIfIsNewForIdAndGetTimestamp(sSmartDataU16 * const me, uint16_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U16_Write(sSmartDataU16 * const me, uint16_t *pValue);
eSmartDataStatus fSmartData_U16_WriteByIndex(uint16_t index, uint16_t *pValue);
eSmartDataStatus fSmartData_U16_WriteWithTimestampUs(sSmartDataU16 * const me, uint16_t *pValue, uint64_t timestampUs);
bool_t fSmartData_U16_HasBeenWrittenSoFar(sSmartDataU16 * const me);
eSmartDataStatus fSmartData_U16_Verify(sSmartDataU16 * const me);
eSmartDataStatus fSmartData_U16_SetMinValue(sSmartDataU16 * const me, uint16_t * pNewValue);
eSmartDataStatus fSmartData_U16_GetMinValue(sSmartDataU16 * const me, uint16_t * pOutValue);
eSmartDataStatus fSmartData_U16_SetMaxValue(sSmartDataU16 * const me, uint16_t * pNewValue);
eSmartDataStatus fSmartData_U16_GetMaxValue(sSmartDataU16 * const me, uint16_t * pOutValue);
eSmartDataStatus fSmartData_U16_SetDefaultValue(sSmartDataU16 * const me, uint16_t * pNewValue);
eSmartDataStatus fSmartData_U16_GetDefaultValue(sSmartDataU16 * const me, uint16_t * pOutValue);
eSmartDataStatus fSmartData_U16_SetResolution(sSmartDataU16 * const me, uint16_t * pNewValue);
eSmartDataStatus fSmartData_U16_GetResolution(sSmartDataU16 * const me, uint16_t * pOutValue);
eSmartDataStatus fSmartData_U16_GetTimestamp(sSmartDataU16 * const me, uint64_t *pOutTsUs);
eSmartDataStatus fSmartData_U16_GetSmartDataSize(sSmartDataU16 * const me, size_t *pOutSize);
eSmartDataStatus fSmartData_U16_GetValueSize(sSmartDataU16 * const me, size_t *pOutSize);

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                INT16_T                                   │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
eSmartDataStatus fSmartData_I16_Ctor(sSmartDataI16 * const me, int16_t minVal, int16_t maxVal, int16_t defaultVal, int16_t resolution, const char *pUnit);
eSmartDataStatus fSmartData_I16_Read(sSmartDataI16 * const me, int16_t * pOutValue);
eSmartDataStatus fSmartData_I16_ReadByIndex(uint16_t index, int16_t * pOutValue);
eSmartDataStatus fSmartData_I16_ReadAndGetTimestampUs(sSmartDataI16 * const me, int16_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I16_ReadIfChanged(sSmartDataI16 * const me, int16_t * pReferenceValue, int16_t * pOutValue);
eSmartDataStatus fSmartData_I16_ReadIfChangedAndGetTimestampUs(sSmartDataI16 * const me, int16_t * pReferenceValue, int16_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I16_ReadIfIsNewerThanTimestampUs(sSmartDataI16 * const me, int16_t * pOutValue, uint64_t timestampUs);
eSmartDataStatus fSmartData_I16_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataI16 * const me, int16_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I16_ReadIfIsUpdatedWithinUs(sSmartDataI16 * const me, int16_t * pOutValue, uint64_t durationUs);
eSmartDataStatus fSmartData_I16_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataI16 * const me, int16_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I16_ReadIfIsNewForId(sSmartDataI16 * const me, int16_t * pOutValue, eSmartDataUserId userId);
eSmartDataStatus fSmartData_I16_ReadIfIsNewForIdAndGetTimestamp(sSmartDataI16 * const me, int16_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I16_Write(sSmartDataI16 * const me, int16_t *pValue);
eSmartDataStatus fSmartData_I16_WriteByIndex(uint16_t index, int16_t *pValue);
eSmartDataStatus fSmartData_I16_WriteWithTimestampUs(sSmartDataI16 * const me, int16_t *pValue, uint64_t timestampUs);
bool_t fSmartData_I16_HasBeenWrittenSoFar(sSmartDataI16 * const me);
eSmartDataStatus fSmartData_I16_Verify(sSmartDataI16 * const me);
eSmartDataStatus fSmartData_I16_SetMinValue(sSmartDataI16 * const me, int16_t * pNewValue);
eSmartDataStatus fSmartData_I16_GetMinValue(sSmartDataI16 * const me, int16_t * pOutValue);
eSmartDataStatus fSmartData_I16_SetMaxValue(sSmartDataI16 * const me, int16_t * pNewValue);
eSmartDataStatus fSmartData_I16_GetMaxValue(sSmartDataI16 * const me, int16_t * pOutValue);
eSmartDataStatus fSmartData_I16_SetDefaultValue(sSmartDataI16 * const me, int16_t * pNewValue);
eSmartDataStatus fSmartData_I16_GetDefaultValue(sSmartDataI16 * const me, int16_t * pOutValue);
eSmartDataStatus fSmartData_I16_SetResolution(sSmartDataI16 * const me, int16_t * pNewValue);
eSmartDataStatus fSmartData_I16_GetResolution(sSmartDataI16 * const me, int16_t * pOutValue);
eSmartDataStatus fSmartData_I16_GetTimestamp(sSmartDataI16 * const me, uint64_t *pOutTsUs);
eSmartDataStatus fSmartData_I16_GetSmartDataSize(sSmartDataI16 * const me, size_t *pOutSize);
eSmartDataStatus fSmartData_I16_GetValueSize(sSmartDataI16 * const me, size_t *pOutSize);

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                UINT32_T                                  │
 * └──────────────────────────────────────────────────────────────────────────┘
 */

eSmartDataStatus fSmartData_U32_Ctor(sSmartDataU32 * const me, uint32_t minVal, uint32_t maxVal, uint32_t defaultVal, uint32_t resolution, const char *pUnit);
eSmartDataStatus fSmartData_U32_Read(sSmartDataU32 * const me, uint32_t * pOutValue);
eSmartDataStatus fSmartData_U32_ReadByIndex(uint16_t index, uint32_t * pOutValue);
eSmartDataStatus fSmartData_U32_ReadAndGetTimestampUs(sSmartDataU32 * const me, uint32_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U32_ReadIfChanged(sSmartDataU32 * const me, uint32_t * pReferenceValue, uint32_t * pOutValue);
eSmartDataStatus fSmartData_U32_ReadIfChangedAndGetTimestampUs(sSmartDataU32 * const me, uint32_t * pReferenceValue, uint32_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U32_ReadIfIsNewerThanTimestampUs(sSmartDataU32 * const me, uint32_t * pOutValue, uint64_t timestampUs);
eSmartDataStatus fSmartData_U32_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataU32 * const me, uint32_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U32_ReadIfIsUpdatedWithinUs(sSmartDataU32 * const me, uint32_t * pOutValue, uint64_t durationUs);
eSmartDataStatus fSmartData_U32_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataU32 * const me, uint32_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U32_ReadIfIsNewForId(sSmartDataU32 * const me, uint32_t * pOutValue, eSmartDataUserId userId);
eSmartDataStatus fSmartData_U32_ReadIfIsNewForIdAndGetTimestamp(sSmartDataU32 * const me, uint32_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U32_Write(sSmartDataU32 * const me, uint32_t *pValue);
eSmartDataStatus fSmartData_U32_WriteByIndex(uint16_t index, uint32_t *pValue);
eSmartDataStatus fSmartData_U32_WriteWithTimestampUs(sSmartDataU32 * const me, uint32_t *pValue, uint64_t timestampUs);
bool_t fSmartData_U32_HasBeenWrittenSoFar(sSmartDataU32 * const me);
eSmartDataStatus fSmartData_U32_Verify(sSmartDataU32 * const me);
eSmartDataStatus fSmartData_U32_SetMinValue(sSmartDataU32 * const me, uint32_t * pNewValue);
eSmartDataStatus fSmartData_U32_GetMinValue(sSmartDataU32 * const me, uint32_t * pOutValue);
eSmartDataStatus fSmartData_U32_SetMaxValue(sSmartDataU32 * const me, uint32_t * pNewValue);
eSmartDataStatus fSmartData_U32_GetMaxValue(sSmartDataU32 * const me, uint32_t * pOutValue);
eSmartDataStatus fSmartData_U32_SetDefaultValue(sSmartDataU32 * const me, uint32_t * pNewValue);
eSmartDataStatus fSmartData_U32_GetDefaultValue(sSmartDataU32 * const me, uint32_t * pOutValue);
eSmartDataStatus fSmartData_U32_SetResolution(sSmartDataU32 * const me, uint32_t * pNewValue);
eSmartDataStatus fSmartData_U32_GetResolution(sSmartDataU32 * const me, uint32_t * pOutValue);
eSmartDataStatus fSmartData_U32_GetTimestamp(sSmartDataU32 * const me, uint64_t *pOutTsUs);
eSmartDataStatus fSmartData_U32_GetSmartDataSize(sSmartDataU32 * const me, size_t *pOutSize);
eSmartDataStatus fSmartData_U32_GetValueSize(sSmartDataU32 * const me, size_t *pOutSize);

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                INT32_T                                   │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
eSmartDataStatus fSmartData_I32_Ctor(sSmartDataI32 * const me, int32_t minVal, int32_t maxVal, int32_t defaultVal, int32_t resolution, const char *pUnit);
eSmartDataStatus fSmartData_I32_Read(sSmartDataI32 * const me, int32_t * pOutValue);
eSmartDataStatus fSmartData_I32_ReadByIndex(uint16_t index, int32_t * pOutValue);
eSmartDataStatus fSmartData_I32_ReadAndGetTimestampUs(sSmartDataI32 * const me, int32_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I32_ReadIfChanged(sSmartDataI32 * const me, int32_t * pReferenceValue, int32_t * pOutValue);
eSmartDataStatus fSmartData_I32_ReadIfChangedAndGetTimestampUs(sSmartDataI32 * const me, int32_t * pReferenceValue, int32_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I32_ReadIfIsNewerThanTimestampUs(sSmartDataI32 * const me, int32_t * pOutValue, uint64_t timestampUs);
eSmartDataStatus fSmartData_I32_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataI32 * const me, int32_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I32_ReadIfIsUpdatedWithinUs(sSmartDataI32 * const me, int32_t * pOutValue, uint64_t durationUs);
eSmartDataStatus fSmartData_I32_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataI32 * const me, int32_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I32_ReadIfIsNewForId(sSmartDataI32 * const me, int32_t * pOutValue, eSmartDataUserId userId);
eSmartDataStatus fSmartData_I32_ReadIfIsNewForIdAndGetTimestamp(sSmartDataI32 * const me, int32_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I32_Write(sSmartDataI32 * const me, int32_t *pValue);
eSmartDataStatus fSmartData_I32_WriteByIndex(uint16_t index, int32_t *pValue);
eSmartDataStatus fSmartData_I32_WriteWithTimestampUs(sSmartDataI32 * const me, int32_t *pValue, uint64_t timestampUs);
bool_t fSmartData_I32_HasBeenWrittenSoFar(sSmartDataI32 * const me);
eSmartDataStatus fSmartData_I32_Verify(sSmartDataI32 * const me);
eSmartDataStatus fSmartData_I32_SetMinValue(sSmartDataI32 * const me, int32_t * pNewValue);
eSmartDataStatus fSmartData_I32_GetMinValue(sSmartDataI32 * const me, int32_t * pOutValue);
eSmartDataStatus fSmartData_I32_SetMaxValue(sSmartDataI32 * const me, int32_t * pNewValue);
eSmartDataStatus fSmartData_I32_GetMaxValue(sSmartDataI32 * const me, int32_t * pOutValue);
eSmartDataStatus fSmartData_I32_SetDefaultValue(sSmartDataI32 * const me, int32_t * pNewValue);
eSmartDataStatus fSmartData_I32_GetDefaultValue(sSmartDataI32 * const me, int32_t * pOutValue);
eSmartDataStatus fSmartData_I32_SetResolution(sSmartDataI32 * const me, int32_t * pNewValue);
eSmartDataStatus fSmartData_I32_GetResolution(sSmartDataI32 * const me, int32_t * pOutValue);
eSmartDataStatus fSmartData_I32_GetTimestamp(sSmartDataI32 * const me, uint64_t *pOutTsUs);
eSmartDataStatus fSmartData_I32_GetSmartDataSize(sSmartDataI32 * const me, size_t *pOutSize);
eSmartDataStatus fSmartData_I32_GetValueSize(sSmartDataI32 * const me, size_t *pOutSize);

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                UINT64_T                                  │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
eSmartDataStatus fSmartData_U64_Ctor(sSmartDataU64 * const me, uint64_t minVal, uint64_t maxVal, uint64_t defaultVal, uint64_t resolution, const char *pUnit);
eSmartDataStatus fSmartData_U64_Read(sSmartDataU64 * const me, uint64_t * pOutValue);
eSmartDataStatus fSmartData_U64_ReadByIndex(uint16_t index, uint64_t * pOutValue);
eSmartDataStatus fSmartData_U64_ReadAndGetTimestampUs(sSmartDataU64 * const me, uint64_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U64_ReadIfChanged(sSmartDataU64 * const me, uint64_t * pReferenceValue, uint64_t * pOutValue);
eSmartDataStatus fSmartData_U64_ReadIfChangedAndGetTimestampUs(sSmartDataU64 * const me, uint64_t * pReferenceValue, uint64_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U64_ReadIfIsNewerThanTimestampUs(sSmartDataU64 * const me, uint64_t * pOutValue, uint64_t timestampUs);
eSmartDataStatus fSmartData_U64_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataU64 * const me, uint64_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U64_ReadIfIsUpdatedWithinUs(sSmartDataU64 * const me, uint64_t * pOutValue, uint64_t durationUs);
eSmartDataStatus fSmartData_U64_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataU64 * const me, uint64_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U64_ReadIfIsNewForId(sSmartDataU64 * const me, uint64_t * pOutValue, eSmartDataUserId userId);
eSmartDataStatus fSmartData_U64_ReadIfIsNewForIdAndGetTimestamp(sSmartDataU64 * const me, uint64_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_U64_Write(sSmartDataU64 * const me, uint64_t *pValue);
eSmartDataStatus fSmartData_U64_WriteByIndex(uint16_t index, uint64_t *pValue);
eSmartDataStatus fSmartData_U64_WriteWithTimestampUs(sSmartDataU64 * const me, uint64_t *pValue, uint64_t timestampUs);
bool_t fSmartData_U64_HasBeenWrittenSoFar(sSmartDataU64 * const me);
eSmartDataStatus fSmartData_U64_Verify(sSmartDataU64 * const me);
eSmartDataStatus fSmartData_U64_SetMinValue(sSmartDataU64 * const me, uint64_t * pNewValue);
eSmartDataStatus fSmartData_U64_GetMinValue(sSmartDataU64 * const me, uint64_t * pOutValue);
eSmartDataStatus fSmartData_U64_SetMaxValue(sSmartDataU64 * const me, uint64_t * pNewValue);
eSmartDataStatus fSmartData_U64_GetMaxValue(sSmartDataU64 * const me, uint64_t * pOutValue);
eSmartDataStatus fSmartData_U64_SetDefaultValue(sSmartDataU64 * const me, uint64_t * pNewValue);
eSmartDataStatus fSmartData_U64_GetDefaultValue(sSmartDataU64 * const me, uint64_t * pOutValue);
eSmartDataStatus fSmartData_U64_SetResolution(sSmartDataU64 * const me, uint64_t * pNewValue);
eSmartDataStatus fSmartData_U64_GetResolution(sSmartDataU64 * const me, uint64_t * pOutValue);
eSmartDataStatus fSmartData_U64_GetTimestamp(sSmartDataU64 * const me, uint64_t *pOutTsUs);
eSmartDataStatus fSmartData_U64_GetSmartDataSize(sSmartDataU64 * const me, size_t *pOutSize);
eSmartDataStatus fSmartData_U64_GetValueSize(sSmartDataU64 * const me, size_t *pOutSize);

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                                INT64_T                                   │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
eSmartDataStatus fSmartData_I64_Ctor(sSmartDataI64 * const me, int64_t minVal, int64_t maxVal, int64_t defaultVal, int64_t resolution, const char *pUnit);
eSmartDataStatus fSmartData_I64_Read(sSmartDataI64 * const me, int64_t * pOutValue);
eSmartDataStatus fSmartData_I64_ReadByIndex(uint16_t index, int64_t * pOutValue);
eSmartDataStatus fSmartData_I64_ReadAndGetTimestampUs(sSmartDataI64 * const me, int64_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I64_ReadIfChanged(sSmartDataI64 * const me, int64_t * pReferenceValue, int64_t * pOutValue);
eSmartDataStatus fSmartData_I64_ReadIfChangedAndGetTimestampUs(sSmartDataI64 * const me, int64_t * pReferenceValue, int64_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I64_ReadIfIsNewerThanTimestampUs(sSmartDataI64 * const me, int64_t * pOutValue, uint64_t timestampUs);
eSmartDataStatus fSmartData_I64_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataI64 * const me, int64_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I64_ReadIfIsUpdatedWithinUs(sSmartDataI64 * const me, int64_t * pOutValue, uint64_t durationUs);
eSmartDataStatus fSmartData_I64_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataI64 * const me, int64_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I64_ReadIfIsNewForId(sSmartDataI64 * const me, int64_t * pOutValue, eSmartDataUserId userId);
eSmartDataStatus fSmartData_I64_ReadIfIsNewForIdAndGetTimestamp(sSmartDataI64 * const me, int64_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_I64_Write(sSmartDataI64 * const me, int64_t *pValue);
eSmartDataStatus fSmartData_I64_WriteByIndex(uint16_t index, int64_t *pValue);
eSmartDataStatus fSmartData_I64_WriteWithTimestampUs(sSmartDataI64 * const me, int64_t *pValue, uint64_t timestampUs);
bool_t fSmartData_I64_HasBeenWrittenSoFar(sSmartDataI64 * const me);
eSmartDataStatus fSmartData_I64_Verify(sSmartDataI64 * const me);
eSmartDataStatus fSmartData_I64_SetMinValue(sSmartDataI64 * const me, int64_t * pNewValue);
eSmartDataStatus fSmartData_I64_GetMinValue(sSmartDataI64 * const me, int64_t * pOutValue);
eSmartDataStatus fSmartData_I64_SetMaxValue(sSmartDataI64 * const me, int64_t * pNewValue);
eSmartDataStatus fSmartData_I64_GetMaxValue(sSmartDataI64 * const me, int64_t * pOutValue);
eSmartDataStatus fSmartData_I64_SetDefaultValue(sSmartDataI64 * const me, int64_t * pNewValue);
eSmartDataStatus fSmartData_I64_GetDefaultValue(sSmartDataI64 * const me, int64_t * pOutValue);
eSmartDataStatus fSmartData_I64_SetResolution(sSmartDataI64 * const me, int64_t * pNewValue);
eSmartDataStatus fSmartData_I64_GetResolution(sSmartDataI64 * const me, int64_t * pOutValue);
eSmartDataStatus fSmartData_I64_GetTimestamp(sSmartDataI64 * const me, uint64_t *pOutTsUs);
eSmartDataStatus fSmartData_I64_GetSmartDataSize(sSmartDataI64 * const me, size_t *pOutSize);
eSmartDataStatus fSmartData_I64_GetValueSize(sSmartDataI64 * const me, size_t *pOutSize);

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                               FLOAT32_T                                  │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
eSmartDataStatus fSmartData_F32_Ctor(sSmartDataF32 * const me, float32_t minVal, float32_t maxVal, float32_t defaultVal, float32_t resolution, const char *pUnit);
eSmartDataStatus fSmartData_F32_Read(sSmartDataF32 * const me, float32_t * pOutValue);
eSmartDataStatus fSmartData_F32_ReadByIndex(uint16_t index, float32_t * pOutValue);
eSmartDataStatus fSmartData_F32_ReadAndGetTimestampUs(sSmartDataF32 * const me, float32_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_F32_ReadIfChanged(sSmartDataF32 * const me, float32_t * pReferenceValue, float32_t * pOutValue);
eSmartDataStatus fSmartData_F32_ReadIfChangedAndGetTimestampUs(sSmartDataF32 * const me, float32_t * pReferenceValue, float32_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_F32_ReadIfIsNewerThanTimestampUs(sSmartDataF32 * const me, float32_t * pOutValue, uint64_t timestampUs);
eSmartDataStatus fSmartData_F32_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataF32 * const me, float32_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_F32_ReadIfIsUpdatedWithinUs(sSmartDataF32* const me, float32_t * pOutValue, uint64_t durationUs);
eSmartDataStatus fSmartData_F32_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataF32* const me, float32_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_F32_ReadIfIsNewForId(sSmartDataF32 * const me, float32_t * pOutValue, eSmartDataUserId userId);
eSmartDataStatus fSmartData_F32_ReadIfIsNewForIdAndGetTimestamp(sSmartDataF32 * const me, float32_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_F32_Write(sSmartDataF32 * const me, float32_t *pValue);
eSmartDataStatus fSmartData_F32_WriteByIndex(uint16_t index, float32_t *pValue);
eSmartDataStatus fSmartData_F32_WriteWithTimestampUs(sSmartDataF32 * const me, float32_t *pValue, uint64_t timestampUs);
bool_t fSmartData_F32_HasBeenWrittenSoFar(sSmartDataF32 * const me);
eSmartDataStatus fSmartData_F32_Verify(sSmartDataF32 * const me);
eSmartDataStatus fSmartData_F32_SetMinValue(sSmartDataF32 * const me, float32_t * pNewValue);
eSmartDataStatus fSmartData_F32_GetMinValue(sSmartDataF32 * const me, float32_t * pOutValue);
eSmartDataStatus fSmartData_F32_SetMaxValue(sSmartDataF32 * const me, float32_t * pNewValue);
eSmartDataStatus fSmartData_F32_GetMaxValue(sSmartDataF32 * const me, float32_t * pOutValue);
eSmartDataStatus fSmartData_F32_SetDefaultValue(sSmartDataF32 * const me, float32_t * pNewValue);
eSmartDataStatus fSmartData_F32_GetDefaultValue(sSmartDataF32 * const me, float32_t * pOutValue);
eSmartDataStatus fSmartData_F32_SetResolution(sSmartDataF32 * const me, float32_t * pNewValue);
eSmartDataStatus fSmartData_F32_GetResolution(sSmartDataF32 * const me, float32_t * pOutValue);
eSmartDataStatus fSmartData_F32_GetTimestamp(sSmartDataF32 * const me, uint64_t *pOutTsUs);
eSmartDataStatus fSmartData_F32_GetSmartDataSize(sSmartDataF32 * const me, size_t *pOutSize);
eSmartDataStatus fSmartData_F32_GetValueSize(sSmartDataF32 * const me, size_t *pOutSize);

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                               FLOAT64_T                                  │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
eSmartDataStatus fSmartData_F64_Ctor(sSmartDataF64 * const me, float64_t minVal, float64_t maxVal, float64_t defaultVal, float64_t resolution, const char *pUnit);
eSmartDataStatus fSmartData_F64_Read(sSmartDataF64 * const me, float64_t * pOutValue);
eSmartDataStatus fSmartData_F64_ReadByIndex(uint16_t index, float64_t * pOutValue);
eSmartDataStatus fSmartData_F64_ReadAndGetTimestampUs(sSmartDataF64 * const me, float64_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_F64_ReadIfChanged(sSmartDataF64 * const me, float64_t * pReferenceValue, float64_t * pOutValue);
eSmartDataStatus fSmartData_F64_ReadIfChangedAndGetTimestampUs(sSmartDataF64 * const me, float64_t * pReferenceValue, float64_t * pOutValue, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_F64_ReadIfIsNewerThanTimestampUs(sSmartDataF64 * const me, float64_t * pOutValue, uint64_t timestampUs);
eSmartDataStatus fSmartData_F64_ReadIfIsNewerThanTimestampUsAndGetTimestampUs(sSmartDataF64 * const me, float64_t * pOutValue, uint64_t timestampUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_F64_ReadIfIsUpdatedWithinUs(sSmartDataF64 * const me, float64_t * pOutValue, uint64_t durationUs);
eSmartDataStatus fSmartData_F64_ReadIfIsUpdatedWithinUsAndGetTimestampUs(sSmartDataF64 * const me, float64_t * pOutValue, uint64_t durationUs, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_F64_ReadIfIsNewForId(sSmartDataF64 * const me, float64_t * pOutValue, eSmartDataUserId userId);
eSmartDataStatus fSmartData_F64_ReadIfIsNewForIdAndGetTimestamp(sSmartDataF64 * const me, float64_t * pOutValue, eSmartDataUserId userId, uint64_t *pOutTimestampUs);
eSmartDataStatus fSmartData_F64_Write(sSmartDataF64 * const me, float64_t *pValue);
eSmartDataStatus fSmartData_F64_WriteByIndex(uint16_t index, float64_t *pValue);
eSmartDataStatus fSmartData_F64_WriteWithTimestampUs(sSmartDataF64 * const me, float64_t *pValue, uint64_t timestampUs);
bool_t fSmartData_F64_HasBeenWrittenSoFar(sSmartDataF64 * const me);
eSmartDataStatus fSmartData_F64_Verify(sSmartDataF64 * const me);
eSmartDataStatus fSmartData_F64_SetMinValue(sSmartDataF64 * const me, float64_t * pNewValue);
eSmartDataStatus fSmartData_F64_GetMinValue(sSmartDataF64 * const me, float64_t * pOutValue);
eSmartDataStatus fSmartData_F64_SetMaxValue(sSmartDataF64 * const me, float64_t * pNewValue);
eSmartDataStatus fSmartData_F64_GetMaxValue(sSmartDataF64 * const me, float64_t * pOutValue);
eSmartDataStatus fSmartData_F64_SetDefaultValue(sSmartDataF64 * const me, float64_t * pNewValue);
eSmartDataStatus fSmartData_F64_GetDefaultValue(sSmartDataF64 * const me, float64_t * pOutValue);
eSmartDataStatus fSmartData_F64_SetResolution(sSmartDataF64 * const me, float64_t * pNewValue);
eSmartDataStatus fSmartData_F64_GetResolution(sSmartDataF64 * const me, float64_t * pOutValue);
eSmartDataStatus fSmartData_F64_GetTimestamp(sSmartDataF64 * const me, uint64_t *pOutTsUs);
eSmartDataStatus fSmartData_F64_GetSmartDataSize(sSmartDataF64 * const me, size_t *pOutSize);
eSmartDataStatus fSmartData_F64_GetValueSize(sSmartDataF64 * const me, size_t *pOutSize);

/* Exported variables ------------------------------------------------------- */

/*
 * ┌──────────────────────────────────────────────────────────────────────────┐
 * │                              ENUMERATIONS                                │
 * └──────────────────────────────────────────────────────────────────────────┘
 */
eSmartDataStatus fSmartData_SetIsValid(void * const me, fSmartDataIsValid pIsValid);

#ifdef __cplusplus
}
#endif

#endif /* SMART_DATA_H */

/* === Copyright (c) 2026 FAS === EOF === */
