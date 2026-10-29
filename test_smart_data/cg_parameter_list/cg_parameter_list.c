/**
  ******************************************************************************
  * @file    cg_parameter_list.c
  * @brief   Generated parameter list and its access functions.
  *
  * This file is generated automatically - DO NOT EDIT IT BY HAND.
  * Generator      : parameter_list_code_generator v01.03.00
  * Generated at   : 2026-10-29 16:54:52 +0330
  * Input file(s)  : parameter_lists/flight_parameters.xml
  * Parameters     : 16 value(s) in 1 structure(s)
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

/* Includes ----------------------------------------------------------------- */
#include "cg_parameter_list.h"

#include <stddef.h>
#include <string.h>

#include "smart_data.h"
#include "cg_smart_data.h"

/* Private defines ---------------------------------------------------------- */
/* Private macros ----------------------------------------------------------- */
/* Private types ------------------------------------------------------------ */
/* Private variables -------------------------------------------------------- */
/* Private functions -------------------------------------------------------- */
/* Exported variables ------------------------------------------------------- */
/**
 * @brief Descriptor of every parameter of the merged parameter list. The order of the entries matches the index macros of 'cg_parameter_list_defines.h'.
 *
 */
const sParameterDescriptor ParameterList[PARAMETER_LIST_QTY] = {
    /* [0] ENGINE_ON */
    {
        .pName = "EngineOn",
        .pUserName = "EngineOn",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_EngineOn,
        .LogId = 100U,
        .TagSystemName = (uint32_t)SYS_AC_MANAGER,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "TRUE while the engine runs."
    },

    /* [1] FLIGHT_MODE */
    {
        .pName = "FlightMode",
        .pUserName = "FlightMode",
        .Type = ePARAMETER_TYPE_SETTING,
        .pSmartData = (void *)&Cg_SmartData_FlightMode,
        .LogId = 101U,
        .TagSystemName = (uint32_t)SYS_AC_AUTOPILOT,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "0 manual, 1 stabilise, 2 hold, 3 mission, 4 return, 5 land."
    },

    /* [2] ELEVATOR_TRIM */
    {
        .pName = "ElevatorTrim",
        .pUserName = "ElevatorTrim",
        .Type = ePARAMETER_TYPE_SETTING,
        .pSmartData = (void *)&Cg_SmartData_ElevatorTrim,
        .LogId = 0U,
        .TagSystemName = (uint32_t)SYS_AC_AUTOPILOT,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)FALSE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Elevator trim."
    },

    /* [3] MOTOR_RPM */
    {
        .pName = "MotorRpm",
        .pUserName = "MotorRpm",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_MotorRpm,
        .LogId = 102U,
        .TagSystemName = (uint32_t)SYS_GOVERNOR,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Engine speed."
    },

    /* [4] CELL_TEMPERATURE_0 */
    {
        .pName = "CellTemperature[0]",
        .pUserName = "CellTemperature",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_CellTemperature[0],
        .LogId = 103U,
        .TagSystemName = (uint32_t)SYS_AC_POWER,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Temperature of one battery cell - one per cell."
    },

    /* [5] CELL_TEMPERATURE_1 */
    {
        .pName = "CellTemperature[1]",
        .pUserName = "CellTemperature",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_CellTemperature[1],
        .LogId = 104U,
        .TagSystemName = (uint32_t)SYS_AC_POWER,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Temperature of one battery cell - one per cell."
    },

    /* [6] CELL_TEMPERATURE_2 */
    {
        .pName = "CellTemperature[2]",
        .pUserName = "CellTemperature",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_CellTemperature[2],
        .LogId = 105U,
        .TagSystemName = (uint32_t)SYS_AC_POWER,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Temperature of one battery cell - one per cell."
    },

    /* [7] CELL_TEMPERATURE_3 */
    {
        .pName = "CellTemperature[3]",
        .pUserName = "CellTemperature",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_CellTemperature[3],
        .LogId = 106U,
        .TagSystemName = (uint32_t)SYS_AC_POWER,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Temperature of one battery cell - one per cell."
    },

    /* [8] FLIGHT_TIME */
    {
        .pName = "FlightTime",
        .pUserName = "FlightTime",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_FlightTime,
        .LogId = 107U,
        .TagSystemName = (uint32_t)SYS_AC_MANAGER,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Time in the air since take-off."
    },

    /* [9] ALTITUDE_CM */
    {
        .pName = "AltitudeCm",
        .pUserName = "AltitudeCm",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_AltitudeCm,
        .LogId = 108U,
        .TagSystemName = (uint32_t)SYS_NAV,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Altitude above sea level."
    },

    /* [10] AIRSPEED */
    {
        .pName = "Airspeed",
        .pUserName = "Airspeed",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_Airspeed,
        .LogId = 109U,
        .TagSystemName = (uint32_t)SYS_NAV,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Indicated airspeed."
    },

    /* [11] HOME_LATITUDE */
    {
        .pName = "HomeLatitude",
        .pUserName = "HomeLatitude",
        .Type = ePARAMETER_TYPE_SETTING,
        .pSmartData = (void *)&Cg_SmartData_HomeLatitude,
        .LogId = 0U,
        .TagSystemName = (uint32_t)SYS_NAV,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)FALSE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Latitude of the home point."
    },

    /* [12] REZA_SAEEDI_BIRTH_YEAR */
    {
        .pName = "RezaSaeedi.BirthYear",
        .pUserName = "",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_RezaSaeedi.BirthYear,
        .LogId = 0U,
        .TagSystemName = (uint32_t)SYS_UNKNOWN,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)FALSE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Year of birth - the default is a placeholder."
    },

    /* [13] REZA_SAEEDI_COFFEE_CUPS_PER_DAY */
    {
        .pName = "RezaSaeedi.CoffeeCupsPerDay",
        .pUserName = "",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_RezaSaeedi.CoffeeCupsPerDay,
        .LogId = 0U,
        .TagSystemName = (uint32_t)SYS_UNKNOWN,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)FALSE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Cups of coffee a day. Even this stops at 20."
    },

    /* [14] REZA_SAEEDI_BUGS_FIXED_TODAY */
    {
        .pName = "RezaSaeedi.BugsFixedToday",
        .pUserName = "",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_RezaSaeedi.BugsFixedToday,
        .LogId = 0U,
        .TagSystemName = (uint32_t)SYS_UNKNOWN,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)FALSE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Bugs fixed today. It only counts up."
    },

    /* [15] REZA_SAEEDI_SLEEP_HOURS */
    {
        .pName = "RezaSaeedi.SleepHours",
        .pUserName = "",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_RezaSaeedi.SleepHours,
        .LogId = 0U,
        .TagSystemName = (uint32_t)SYS_UNKNOWN,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)FALSE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = "Hours of sleep last night."
    }
};

/*
  ==============================================================================
                        ##### Exported Functions #####
  ==============================================================================
*/

/**
 * @brief Initialises the parameter list and every smart-data object.
 *
 * @return uint8_t 0 on success, otherwise a non-zero error code.
 */
uint8_t fParameterList_Init(void) {

    uint8_t result = 0U;

    result = fCgSmartData_Init();
    if (result != 0U) {
        return result;
    }

    result = fParameterList_InitCompletedCallback();
    if (result != 0U) {
        return result;
    }

    return result;

}

/**
 * @brief Called once the parameter list has been initialised.
 *
 * @note  Implement this function in the application layer without the weak specifier to hook into the initialisation.
 * @return uint8_t 0 on success, otherwise a non-zero error code.
 */
PARAMETER_LIST_WEAK uint8_t fParameterList_InitCompletedCallback(void) {

    return 0U;

}

/**
 * @brief Returns the number of parameters in the list.
 *
 * @return uint16_t Always PARAMETER_LIST_QTY.
 */
uint16_t fParameterList_GetQuantity(void) {

    return (uint16_t)PARAMETER_LIST_QTY;

}

/**
 * @brief Returns the descriptor of the parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @return const sParameterDescriptor* NULL when the index is out of range.
 */
const sParameterDescriptor * fParameterList_GetByIndex(uint16_t index) {

    if (index >= (uint16_t)PARAMETER_LIST_QTY) {
        return NULL;
    }

    return &ParameterList[index];

}

/**
 * @brief Returns the descriptor of the parameter called *pName*.
 *
 * @param pName Name of the parameter; a field of a structure is  *              listed under its dotted name, e.g. "Position.Home.Lat".
 * @return const sParameterDescriptor* NULL when no such parameter exists.
 */
const sParameterDescriptor * fParameterList_GetByName(const char *pName) {

    uint16_t index = 0U;

    if (pName == NULL) {
        return NULL;
    }

    for (index = 0U; index < (uint16_t)PARAMETER_LIST_QTY; index++) {
        if (strcmp(ParameterList[index].pName, pName) == 0) {
            return &ParameterList[index];
        }
    }

    return NULL;

}

/**
 * @brief Reads the value of the bool_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pOutValue Where the value is written.
 * @return eSmartDataStatus eSMART_DATA_OK when the value came back,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pOutValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a bool_t.
 */
eSmartDataStatus fParameterList_B8_ReadByIndex(uint16_t index, bool_t *pOutValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_B8) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_B8_Read((sSmartDataB8 *)pDescriptor->pSmartData, pOutValue);

}

/**
 * @brief Writes the value of the bool_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pValue The value to write.
 * @return eSmartDataStatus eSMART_DATA_OK when the value was stored,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a bool_t.
 */
eSmartDataStatus fParameterList_B8_WriteByIndex(uint16_t index, bool_t *pValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_B8) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_B8_Write((sSmartDataB8 *)pDescriptor->pSmartData, pValue);

}

/**
 * @brief Reads the value of the uint8_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pOutValue Where the value is written.
 * @return eSmartDataStatus eSMART_DATA_OK when the value came back,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pOutValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a uint8_t.
 */
eSmartDataStatus fParameterList_U8_ReadByIndex(uint16_t index, uint8_t *pOutValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_U8) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_U8_Read((sSmartDataU8 *)pDescriptor->pSmartData, pOutValue);

}

/**
 * @brief Writes the value of the uint8_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pValue The value to write.
 * @return eSmartDataStatus eSMART_DATA_OK when the value was stored,
 *         eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE when it was refused,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a uint8_t.
 */
eSmartDataStatus fParameterList_U8_WriteByIndex(uint16_t index, uint8_t *pValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_U8) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_U8_Write((sSmartDataU8 *)pDescriptor->pSmartData, pValue);

}

/**
 * @brief Reads the value of the int8_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pOutValue Where the value is written.
 * @return eSmartDataStatus eSMART_DATA_OK when the value came back,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pOutValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a int8_t.
 */
eSmartDataStatus fParameterList_I8_ReadByIndex(uint16_t index, int8_t *pOutValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_I8) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_I8_Read((sSmartDataI8 *)pDescriptor->pSmartData, pOutValue);

}

/**
 * @brief Writes the value of the int8_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pValue The value to write.
 * @return eSmartDataStatus eSMART_DATA_OK when the value was stored,
 *         eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE when it was refused,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a int8_t.
 */
eSmartDataStatus fParameterList_I8_WriteByIndex(uint16_t index, int8_t *pValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_I8) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_I8_Write((sSmartDataI8 *)pDescriptor->pSmartData, pValue);

}

/**
 * @brief Reads the value of the uint16_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pOutValue Where the value is written.
 * @return eSmartDataStatus eSMART_DATA_OK when the value came back,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pOutValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a uint16_t.
 */
eSmartDataStatus fParameterList_U16_ReadByIndex(uint16_t index, uint16_t *pOutValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_U16) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_U16_Read((sSmartDataU16 *)pDescriptor->pSmartData, pOutValue);

}

/**
 * @brief Writes the value of the uint16_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pValue The value to write.
 * @return eSmartDataStatus eSMART_DATA_OK when the value was stored,
 *         eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE when it was refused,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a uint16_t.
 */
eSmartDataStatus fParameterList_U16_WriteByIndex(uint16_t index, uint16_t *pValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_U16) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_U16_Write((sSmartDataU16 *)pDescriptor->pSmartData, pValue);

}

/**
 * @brief Reads the value of the int16_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pOutValue Where the value is written.
 * @return eSmartDataStatus eSMART_DATA_OK when the value came back,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pOutValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a int16_t.
 */
eSmartDataStatus fParameterList_I16_ReadByIndex(uint16_t index, int16_t *pOutValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_I16) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_I16_Read((sSmartDataI16 *)pDescriptor->pSmartData, pOutValue);

}

/**
 * @brief Writes the value of the int16_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pValue The value to write.
 * @return eSmartDataStatus eSMART_DATA_OK when the value was stored,
 *         eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE when it was refused,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a int16_t.
 */
eSmartDataStatus fParameterList_I16_WriteByIndex(uint16_t index, int16_t *pValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_I16) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_I16_Write((sSmartDataI16 *)pDescriptor->pSmartData, pValue);

}

/**
 * @brief Reads the value of the uint32_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pOutValue Where the value is written.
 * @return eSmartDataStatus eSMART_DATA_OK when the value came back,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pOutValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a uint32_t.
 */
eSmartDataStatus fParameterList_U32_ReadByIndex(uint16_t index, uint32_t *pOutValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_U32) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_U32_Read((sSmartDataU32 *)pDescriptor->pSmartData, pOutValue);

}

/**
 * @brief Writes the value of the uint32_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pValue The value to write.
 * @return eSmartDataStatus eSMART_DATA_OK when the value was stored,
 *         eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE when it was refused,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a uint32_t.
 */
eSmartDataStatus fParameterList_U32_WriteByIndex(uint16_t index, uint32_t *pValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_U32) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_U32_Write((sSmartDataU32 *)pDescriptor->pSmartData, pValue);

}

/**
 * @brief Reads the value of the int32_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pOutValue Where the value is written.
 * @return eSmartDataStatus eSMART_DATA_OK when the value came back,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pOutValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a int32_t.
 */
eSmartDataStatus fParameterList_I32_ReadByIndex(uint16_t index, int32_t *pOutValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_I32) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_I32_Read((sSmartDataI32 *)pDescriptor->pSmartData, pOutValue);

}

/**
 * @brief Writes the value of the int32_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pValue The value to write.
 * @return eSmartDataStatus eSMART_DATA_OK when the value was stored,
 *         eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE when it was refused,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a int32_t.
 */
eSmartDataStatus fParameterList_I32_WriteByIndex(uint16_t index, int32_t *pValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_I32) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_I32_Write((sSmartDataI32 *)pDescriptor->pSmartData, pValue);

}

/**
 * @brief Reads the value of the uint64_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pOutValue Where the value is written.
 * @return eSmartDataStatus eSMART_DATA_OK when the value came back,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pOutValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a uint64_t.
 */
eSmartDataStatus fParameterList_U64_ReadByIndex(uint16_t index, uint64_t *pOutValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_U64) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_U64_Read((sSmartDataU64 *)pDescriptor->pSmartData, pOutValue);

}

/**
 * @brief Writes the value of the uint64_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pValue The value to write.
 * @return eSmartDataStatus eSMART_DATA_OK when the value was stored,
 *         eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE when it was refused,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a uint64_t.
 */
eSmartDataStatus fParameterList_U64_WriteByIndex(uint16_t index, uint64_t *pValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_U64) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_U64_Write((sSmartDataU64 *)pDescriptor->pSmartData, pValue);

}

/**
 * @brief Reads the value of the int64_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pOutValue Where the value is written.
 * @return eSmartDataStatus eSMART_DATA_OK when the value came back,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pOutValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a int64_t.
 */
eSmartDataStatus fParameterList_I64_ReadByIndex(uint16_t index, int64_t *pOutValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_I64) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_I64_Read((sSmartDataI64 *)pDescriptor->pSmartData, pOutValue);

}

/**
 * @brief Writes the value of the int64_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pValue The value to write.
 * @return eSmartDataStatus eSMART_DATA_OK when the value was stored,
 *         eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE when it was refused,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a int64_t.
 */
eSmartDataStatus fParameterList_I64_WriteByIndex(uint16_t index, int64_t *pValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_I64) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_I64_Write((sSmartDataI64 *)pDescriptor->pSmartData, pValue);

}

/**
 * @brief Reads the value of the float32_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pOutValue Where the value is written.
 * @return eSmartDataStatus eSMART_DATA_OK when the value came back,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pOutValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a float32_t.
 */
eSmartDataStatus fParameterList_F32_ReadByIndex(uint16_t index, float32_t *pOutValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_F32) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_F32_Read((sSmartDataF32 *)pDescriptor->pSmartData, pOutValue);

}

/**
 * @brief Writes the value of the float32_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pValue The value to write.
 * @return eSmartDataStatus eSMART_DATA_OK when the value was stored,
 *         eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE when it was refused,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a float32_t.
 */
eSmartDataStatus fParameterList_F32_WriteByIndex(uint16_t index, float32_t *pValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_F32) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_F32_Write((sSmartDataF32 *)pDescriptor->pSmartData, pValue);

}

/**
 * @brief Reads the value of the float64_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pOutValue Where the value is written.
 * @return eSmartDataStatus eSMART_DATA_OK when the value came back,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pOutValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a float64_t.
 */
eSmartDataStatus fParameterList_F64_ReadByIndex(uint16_t index, float64_t *pOutValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_F64) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_F64_Read((sSmartDataF64 *)pDescriptor->pSmartData, pOutValue);

}

/**
 * @brief Writes the value of the float64_t parameter at *index*.
 *
 * @param index Index of the parameter, see 'cg_parameter_list_defines.h'.
 * @param pValue The value to write.
 * @return eSmartDataStatus eSMART_DATA_OK when the value was stored,
 *         eSMART_DATA_ERROR_VALUE_OUT_OF_RANGE when it was refused,
 *         eSMART_DATA_ERROR_NULL_POINTER when the index is out of range or pValue is NULL,
 *         eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED when that parameter is not a float64_t.
 */
eSmartDataStatus fParameterList_F64_WriteByIndex(uint16_t index, float64_t *pValue) {

    const sParameterDescriptor *pDescriptor = fParameterList_GetByIndex(index);

    if (pDescriptor == NULL) {
        return eSMART_DATA_ERROR_NULL_POINTER;
    }

    if (((const sSmartDataCore *)pDescriptor->pSmartData)->TypeInfo.Type != eSMART_DATA_TYPE_F64) {
        return eSMART_DATA_ERROR_DATA_TYPE_NOT_SUPPORTED;
    }

    return fSmartData_F64_Write((sSmartDataF64 *)pDescriptor->pSmartData, pValue);

}

/**
 * @brief Total number of bytes reserved by the 'SystemName' tag.
 *
 * @note  This is the sum over every parameter that carries the tag, each one taking sizeof(value) x array size bytes.
 * @return uint32_t Always PARAMETER_LIST_TAG_SYSTEM_NAME_SIZE.
 */
uint32_t fParameterList_GetSystemNameSize(void) {

    return (uint32_t)PARAMETER_LIST_TAG_SYSTEM_NAME_SIZE;

}

/**
 * @brief Total number of bytes reserved by the 'Loggable' tag.
 *
 * @note  This is the sum over every parameter that carries the tag, each one taking sizeof(value) x array size bytes.
 * @return uint32_t Always PARAMETER_LIST_TAG_LOGGABLE_SIZE.
 */
uint32_t fParameterList_GetLoggableSize(void) {

    return (uint32_t)PARAMETER_LIST_TAG_LOGGABLE_SIZE;

}

/**
 * @brief Total number of bytes reserved by the 'ParamMode' tag.
 *
 * @note  This is the sum over every parameter that carries the tag, each one taking sizeof(value) x array size bytes.
 * @return uint32_t Always PARAMETER_LIST_TAG_PARAM_MODE_SIZE.
 */
uint32_t fParameterList_GetParamModeSize(void) {

    return (uint32_t)PARAMETER_LIST_TAG_PARAM_MODE_SIZE;

}

/*
  ==============================================================================
                        ##### Private Functions #####
  ==============================================================================
*/

/* === Copyright (c) 2026 FAS === EOF === */
