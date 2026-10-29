/**
  ******************************************************************************
  * @file    cg_smart_data.h
  * @brief   Smart-data objects that hold the value of every parameter.
  *
  * This file is generated automatically - DO NOT EDIT IT BY HAND.
  * Generator      : parameter_list_code_generator v01.03.00
  * Generated at   : 2026-10-29 17:01:39 +0330
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

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef CG_SMART_DATA_H
#define CG_SMART_DATA_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ----------------------------------------------------------------- */
#include "smart_data.h"
#include "cg_parameter_list_defines.h"
#include "cg_parameter_list_types.h"

/* Exported defines --------------------------------------------------------- */
/* Exported macros ---------------------------------------------------------- */
/* Exported types ----------------------------------------------------------- */
/* Exported functions ------------------------------------------------------- */
uint8_t fCgSmartData_Init(void);

/* Exported variables ------------------------------------------------------- */
extern sSmartDataB8 Cg_SmartData_EngineOn;  /*!< TRUE while the engine runs. */
extern sSmartDataU8 Cg_SmartData_FlightMode;  /*!< 0 manual, 1 stabilise, 2 hold, 3 mission, 4 return, 5 land. */
extern sSmartDataI8 Cg_SmartData_ElevatorTrim;  /*!< [deg] Elevator trim. */
extern sSmartDataU16 Cg_SmartData_MotorRpm;  /*!< [rpm] Engine speed. */
extern sSmartDataI16 Cg_SmartData_CellTemperature[CELL_TEMPERATURE_ARRAY_SIZE];  /*!< [degC] Temperature of one battery cell - one per cell. */
extern sSmartDataU32 Cg_SmartData_FlightTime;  /*!< [s] Time in the air since take-off. */
extern sSmartDataI32 Cg_SmartData_AltitudeCm;  /*!< [cm] Altitude above sea level. */
extern sSmartDataF32 Cg_SmartData_Airspeed;  /*!< [m/s] Indicated airspeed. */
extern sSmartDataF64 Cg_SmartData_HomeLatitude;  /*!< [deg] Latitude of the home point. */
extern sCgStruct_sRezaSaeedi Cg_SmartData_RezaSaeedi;  /*!< The one behind the tool, as a structure. */

#ifdef __cplusplus
}
#endif

#endif /* CG_SMART_DATA_H */

/* === Copyright (c) 2026 FAS === EOF === */
