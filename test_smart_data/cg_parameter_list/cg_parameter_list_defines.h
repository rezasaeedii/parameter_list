/**
  ******************************************************************************
  * @file    cg_parameter_list_defines.h
  * @brief   Quantities, parameter indices, tag sizes, system names and parameter modes.
  *
  * This file is generated automatically - DO NOT EDIT IT BY HAND.
  * Generator      : parameter_list_code_generator v01.01.01
  * Generated at   : 2026-10-29 16:47:37 +0330
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
#ifndef CG_PARAMETER_LIST_DEFINES_H
#define CG_PARAMETER_LIST_DEFINES_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ----------------------------------------------------------------- */
#include <stdint.h>

/* Exported defines --------------------------------------------------------- */
/* Number of parameters in the parameter list */
#define PARAMETER_LIST_QTY  (16U)  /*!< Number of enabled parameters */

/* Index of every parameter inside the parameter list */
#define ENGINE_ON                        (0U)   /*!< bool_t */
#define FLIGHT_MODE                      (1U)   /*!< uint8_t */
#define ELEVATOR_TRIM                    (2U)   /*!< int8_t [deg] */
#define MOTOR_RPM                        (3U)   /*!< uint16_t [rpm] */
#define CELL_TEMPERATURE_0               (4U)   /*!< int16_t (element 0 of 4) [degC] */
#define CELL_TEMPERATURE_1               (5U)   /*!< int16_t (element 1 of 4) [degC] */
#define CELL_TEMPERATURE_2               (6U)   /*!< int16_t (element 2 of 4) [degC] */
#define CELL_TEMPERATURE_3               (7U)   /*!< int16_t (element 3 of 4) [degC] */
#define FLIGHT_TIME                      (8U)   /*!< uint32_t [s] */
#define ALTITUDE_CM                      (9U)   /*!< int32_t [cm] */
#define AIRSPEED                         (10U)  /*!< float32_t [m/s] */
#define HOME_LATITUDE                    (11U)  /*!< float64_t [deg] */
#define REZA_SAEEDI_BIRTH_YEAR           (12U)  /*!< uint16_t */
#define REZA_SAEEDI_COFFEE_CUPS_PER_DAY  (13U)  /*!< uint8_t [cup] */
#define REZA_SAEEDI_BUGS_FIXED_TODAY     (14U)  /*!< uint32_t */
#define REZA_SAEEDI_SLEEP_HOURS          (15U)  /*!< float32_t [h] */

/* Array size of every array parameter */
#define CELL_TEMPERATURE_ARRAY_SIZE  (4U)  /*!< Number of elements of 'CellTemperature' */

/* Total size used by every tag */
#define PARAMETER_LIST_TAG_SYSTEM_NAME_SIZE  (44U)  /*!< Bytes used by tag 'SystemName' (16 parameter(s)) */
#define PARAMETER_LIST_TAG_LOGGABLE_SIZE     (24U)  /*!< Bytes used by tag 'Loggable' (10 parameter(s)) */
#define PARAMETER_LIST_TAG_PARAM_MODE_SIZE   (44U)  /*!< Bytes used by tag 'ParamMode' (16 parameter(s)) */

/* Values of the 'SYSTEM NAMES' drop-down list (kept where already defined) */
#ifndef SYS_UNKNOWN
#define SYS_UNKNOWN          (0U)
#endif
#ifndef SYS_GS_COMPUTER
#define SYS_GS_COMPUTER      (1U)
#endif
#ifndef SYS_GS_MANAGER
#define SYS_GS_MANAGER       (2U)
#endif
#ifndef SYS_GS_PO
#define SYS_GS_PO            (3U)
#endif
#ifndef SYS_ANTENNA_TRACKER
#define SYS_ANTENNA_TRACKER  (4U)
#endif
#ifndef SYS_AC_MANAGER
#define SYS_AC_MANAGER       (5U)
#endif
#ifndef SYS_AC_POWER
#define SYS_AC_POWER         (6U)
#endif
#ifndef SYS_AC_AUTOPILOT
#define SYS_AC_AUTOPILOT     (7U)
#endif
#ifndef SYS_GIMBAL
#define SYS_GIMBAL           (8U)
#endif
#ifndef SYS_LOCK_TRACK
#define SYS_LOCK_TRACK       (9U)
#endif
#ifndef SYS_LINK_GS
#define SYS_LINK_GS          (10U)
#endif
#ifndef SYS_GS_USB2CAN
#define SYS_GS_USB2CAN       (11U)
#endif
#ifndef SYS_LINK_AIR
#define SYS_LINK_AIR         (12U)
#endif
#ifndef SYS_BOOTLOADER
#define SYS_BOOTLOADER       (13U)
#endif
#ifndef SYS_LINK_BOX
#define SYS_LINK_BOX         (14U)
#endif
#ifndef SYS_GOVERNOR
#define SYS_GOVERNOR         (15U)
#endif
#ifndef SYS_NAV
#define SYS_NAV              (16U)
#endif
#ifndef SYS_AND
#define SYS_AND              (17U)
#endif
#ifndef SYS_VNS
#define SYS_VNS              (18U)
#endif
#ifndef SYS_RHS
#define SYS_RHS              (19U)
#endif
#ifndef SYS_AUP
#define SYS_AUP              (20U)
#endif
#ifndef Suuu
#define Suuu                 (56652U)
#endif
#ifndef dsax
#define dsax                 (56653U)
#endif

/* Values of the 'PARAM MODES' drop-down list (kept where already defined) */
#ifndef PARAM_MODE_NONE
#define PARAM_MODE_NONE          (0U)
#endif
#ifndef PARAM_MODE_USER
#define PARAM_MODE_USER          (1U)
#endif
#ifndef PARAM_MODE_READ_ONLY
#define PARAM_MODE_READ_ONLY     (2U)
#endif
#ifndef PARAM_MODE_PRODUCT_TYPE
#define PARAM_MODE_PRODUCT_TYPE  (3U)
#endif
#ifndef PARAM_MODE_FACTORY
#define PARAM_MODE_FACTORY       (4U)
#endif
#ifndef PARAM_MODE_CALIB
#define PARAM_MODE_CALIB         (5U)
#endif
#ifndef PARAM_MODE_TEMPORARY
#define PARAM_MODE_TEMPORARY     (6U)
#endif

/* Exported macros ---------------------------------------------------------- */
/* Exported types ----------------------------------------------------------- */
/* Exported functions ------------------------------------------------------- */
/* Exported variables ------------------------------------------------------- */

#ifdef __cplusplus
}
#endif

#endif /* CG_PARAMETER_LIST_DEFINES_H */

/* === Copyright (c) 2026 FAS === EOF === */
