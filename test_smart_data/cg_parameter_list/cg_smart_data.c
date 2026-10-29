/**
  ******************************************************************************
  * @file    cg_smart_data.c
  * @brief   Definition and construction of the generated smart-data objects.
  *
  * This file is generated automatically - DO NOT EDIT IT BY HAND.
  * Generator      : parameter_list_code_generator v01.03.01
  * Generated at   : 2026-10-29 19:44:49 +0330
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
#include "cg_smart_data.h"
#include "smart_data.h"

/* Private defines ---------------------------------------------------------- */
/* Private macros ----------------------------------------------------------- */
/* Private types ------------------------------------------------------------ */
/* Private variables -------------------------------------------------------- */
/* Private functions -------------------------------------------------------- */
/* Exported variables ------------------------------------------------------- */
sSmartDataB8 Cg_SmartData_EngineOn;
sSmartDataU8 Cg_SmartData_FlightMode;
sSmartDataI8 Cg_SmartData_ElevatorTrim;
sSmartDataU16 Cg_SmartData_MotorRpm;
sSmartDataI16 Cg_SmartData_CellTemperature[CELL_TEMPERATURE_ARRAY_SIZE];
sSmartDataU32 Cg_SmartData_FlightTime;
sSmartDataI32 Cg_SmartData_AltitudeCm;
sSmartDataF32 Cg_SmartData_Airspeed;
sSmartDataF64 Cg_SmartData_HomeLatitude;
sCgStruct_sRezaSaeedi Cg_SmartData_RezaSaeedi;

/*
  ==============================================================================
                        ##### Exported Functions #####
  ==============================================================================
*/

/**
 * @brief Constructs every generated smart-data object.
 *
 * @return uint8_t 0 on success, otherwise the failing eSmartDataStatus value.
 */
uint8_t fCgSmartData_Init(void) {

    eSmartDataStatus status = eSMART_DATA_OK;
    uint16_t index = 0U;

    status = fSmartData_B8_Ctor(&Cg_SmartData_EngineOn, FALSE);
    if (status != eSMART_DATA_OK) {
        return (uint8_t)status;
    }

    status = fSmartData_U8_Ctor(&Cg_SmartData_FlightMode, 0U, 5U, 0U, 1U, "");
    if (status != eSMART_DATA_OK) {
        return (uint8_t)status;
    }

    status = fSmartData_I8_Ctor(&Cg_SmartData_ElevatorTrim, (-20), 20, 0, 1, "deg");
    if (status != eSMART_DATA_OK) {
        return (uint8_t)status;
    }

    status = fSmartData_U16_Ctor(&Cg_SmartData_MotorRpm, 0U, 12000U, 0U, 1U, "rpm");
    if (status != eSMART_DATA_OK) {
        return (uint8_t)status;
    }

    for (index = 0U; index < CELL_TEMPERATURE_ARRAY_SIZE; index++) {
        status = fSmartData_I16_Ctor(&Cg_SmartData_CellTemperature[index], (-40), 125, 25, 1, "degC");
        if (status != eSMART_DATA_OK) {
            return (uint8_t)status;
        }
    }

    status = fSmartData_U32_Ctor(&Cg_SmartData_FlightTime, 0UL, 4000000000UL, 0UL, 1UL, "s");
    if (status != eSMART_DATA_OK) {
        return (uint8_t)status;
    }

    status = fSmartData_I32_Ctor(&Cg_SmartData_AltitudeCm, (-50000L), 1000000L, 0L, 1L, "cm");
    if (status != eSMART_DATA_OK) {
        return (uint8_t)status;
    }

    status = fSmartData_F32_Ctor(&Cg_SmartData_Airspeed, 0.0f, 120.0f, 0.0f, 0.1f, "m/s");
    if (status != eSMART_DATA_OK) {
        return (uint8_t)status;
    }

    status = fSmartData_F64_Ctor(&Cg_SmartData_HomeLatitude, -90.0, 90.0, 35.6892, 1.0e-07, "deg");
    if (status != eSMART_DATA_OK) {
        return (uint8_t)status;
    }

    status = fSmartData_U16_Ctor(&Cg_SmartData_RezaSaeedi.BirthYear, 1900U, 2100U, 2000U, 1U, "");
    if (status != eSMART_DATA_OK) {
        return (uint8_t)status;
    }

    status = fSmartData_U8_Ctor(&Cg_SmartData_RezaSaeedi.CoffeeCupsPerDay, 0U, 20U, 3U, 1U, "cup");
    if (status != eSMART_DATA_OK) {
        return (uint8_t)status;
    }

    status = fSmartData_U32_Ctor(&Cg_SmartData_RezaSaeedi.BugsFixedToday, 0UL, 4294967295UL, 0UL, 1UL, "");
    if (status != eSMART_DATA_OK) {
        return (uint8_t)status;
    }

    status = fSmartData_F32_Ctor(&Cg_SmartData_RezaSaeedi.SleepHours, 0.0f, 24.0f, 4.5f, 0.5f, "h");
    if (status != eSMART_DATA_OK) {
        return (uint8_t)status;
    }

    return (uint8_t)status;

}

/*
  ==============================================================================
                        ##### Private Functions #####
  ==============================================================================
*/

/* === Copyright (c) 2026 FAS === EOF === */
