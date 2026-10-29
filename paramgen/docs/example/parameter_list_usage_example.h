/**
  ******************************************************************************
  * @file    parameter_list_usage_example.h
  * @brief   How firmware uses the code the tool generates.
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
#ifndef PARAMETER_LIST_USAGE_EXAMPLE_H
#define PARAMETER_LIST_USAGE_EXAMPLE_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ----------------------------------------------------------------- */
#include "smart_data.h"
#include "parameter_descriptor.h"

/* Exported functions ------------------------------------------------------- */
uint8_t fExample_Start(void);

eSmartDataStatus fExample_Read(float32_t *pAirspeed);

eSmartDataStatus fExample_Write(float32_t airspeed);

eParameterDescriptorStatus fExample_WriteAndNotify(float32_t airspeed);

eSmartDataStatus fExample_StructAccess(uint8_t *pCoffeeCups);

uint16_t fExample_ArrayAccess(void);

uint16_t fExample_WalkTable(void);

bool_t fExample_ReadIfNew(float32_t *pAirspeed);

#ifdef __cplusplus
}
#endif

#endif /* PARAMETER_LIST_USAGE_EXAMPLE_H */

/* === Copyright (c) 2026 FAS === EOF === */
