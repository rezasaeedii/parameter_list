/**
  ******************************************************************************
  * @file    cg_parameter_list.c
  * @brief   Generated parameter list and its access functions.
  *
  * This file is generated automatically - DO NOT EDIT IT BY HAND.
  * Generator      : parameter_list_code_generator v01.03.01
  * Generated at   : 2026-10-30 08:55:22 +0330
  * Input file(s)  : parameter_lists/flight_parameters.xml
  * Parameters     : 23 value(s) in 1 structure(s)
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
    },

    /* [16] NOUROOZ_0 */
    {
        .pName = "nourooz[0]",
        .pUserName = "hafte",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_nourooz[0],
        .LogId = 110U,
        .TagSystemName = (uint32_t)SYS_UNKNOWN,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = ""
    },

    /* [17] NOUROOZ_1 */
    {
        .pName = "nourooz[1]",
        .pUserName = "hafte",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_nourooz[1],
        .LogId = 111U,
        .TagSystemName = (uint32_t)SYS_UNKNOWN,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = ""
    },

    /* [18] NOUROOZ_2 */
    {
        .pName = "nourooz[2]",
        .pUserName = "hafte",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_nourooz[2],
        .LogId = 112U,
        .TagSystemName = (uint32_t)SYS_UNKNOWN,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = ""
    },

    /* [19] NOUROOZ_3 */
    {
        .pName = "nourooz[3]",
        .pUserName = "hafte",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_nourooz[3],
        .LogId = 113U,
        .TagSystemName = (uint32_t)SYS_UNKNOWN,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = ""
    },

    /* [20] NOUROOZ_4 */
    {
        .pName = "nourooz[4]",
        .pUserName = "hafte",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_nourooz[4],
        .LogId = 114U,
        .TagSystemName = (uint32_t)SYS_UNKNOWN,
        .TagResetProof = (uint32_t)FALSE,
        .TagLoggable = (uint32_t)TRUE,
        .TagLogEncryption = (uint32_t)FALSE,
        .TagParamMode = (uint32_t)PARAM_MODE_NONE,
        .Tag1 = 0U,
        .Tag2 = 0U,
        .Tag3 = 0U,
        .Tag4 = 0U,
        .pDescription = ""
    },

    /* [21] NOUROZ2222 */
    {
        .pName = "nouroz2222",
        .pUserName = "",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_nouroz2222,
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
        .pDescription = ""
    },

    /* [22] SALAM */
    {
        .pName = "salam",
        .pUserName = "",
        .Type = ePARAMETER_TYPE_MONITORING,
        .pSmartData = (void *)&Cg_SmartData_salam,
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
        .pDescription = ""
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
