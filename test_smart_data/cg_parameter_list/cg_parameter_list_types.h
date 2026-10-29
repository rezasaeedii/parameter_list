/**
  ******************************************************************************
  * @file    cg_parameter_list_types.h
  * @brief   Structure types generated from the structure types of the parameter list.
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
#ifndef CG_PARAMETER_LIST_TYPES_H
#define CG_PARAMETER_LIST_TYPES_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ----------------------------------------------------------------- */
#include "smart_data.h"
#include "cg_parameter_list_defines.h"

/* Exported defines --------------------------------------------------------- */
/* Exported macros ---------------------------------------------------------- */
/* Exported types ----------------------------------------------------------- */
/**
 * @brief Structure type 'sRezaSaeedi'.
 *
 * @note  Used by: RezaSaeedi
 */
typedef struct {

    sSmartDataU16 BirthYear;
    sSmartDataU8  CoffeeCupsPerDay;
    sSmartDataU32 BugsFixedToday;
    sSmartDataF32 SleepHours;

} sCgStruct_sRezaSaeedi;

/* Exported functions ------------------------------------------------------- */
/* Exported variables ------------------------------------------------------- */

#ifdef __cplusplus
}
#endif

#endif /* CG_PARAMETER_LIST_TYPES_H */

/* === Copyright (c) 2026 FAS === EOF === */
