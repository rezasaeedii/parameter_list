/**
  ******************************************************************************
  * @file    cg_parameter_list.h
  * @brief   Generated parameter list and its access functions.
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
#ifndef CG_PARAMETER_LIST_H
#define CG_PARAMETER_LIST_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ----------------------------------------------------------------- */
#include "parameter_descriptor.h"
#include "cg_parameter_list_defines.h"
#include "cg_smart_data.h"
#include "cg_parameter_list_types.h"

/* Exported defines --------------------------------------------------------- */
/* Exported macros ---------------------------------------------------------- */
/**
 * @brief Compiler independent 'weak' attribute.
 *
 */
#ifndef PARAMETER_LIST_WEAK
  #if defined(__GNUC__) || defined(__clang__) || defined(__ARMCC_VERSION)
    #define PARAMETER_LIST_WEAK  __attribute__((weak))
  #elif defined(__ICCARM__)
    #define PARAMETER_LIST_WEAK  __weak
  #else
    #define PARAMETER_LIST_WEAK
  #endif
#endif  /* PARAMETER_LIST_WEAK */

/* Exported types ----------------------------------------------------------- */
/* Exported functions ------------------------------------------------------- */
uint8_t fParameterList_Init(void);
PARAMETER_LIST_WEAK uint8_t fParameterList_InitCompletedCallback(void);
uint16_t fParameterList_GetQuantity(void);
const sParameterDescriptor * fParameterList_GetByIndex(uint16_t index);
const sParameterDescriptor * fParameterList_GetByName(const char *pName);

/* Read or write the value at an index, one pair for every data type. */
eSmartDataStatus fParameterList_B8_ReadByIndex(uint16_t index, bool_t *pOutValue);
eSmartDataStatus fParameterList_B8_WriteByIndex(uint16_t index, bool_t *pValue);
eSmartDataStatus fParameterList_U8_ReadByIndex(uint16_t index, uint8_t *pOutValue);
eSmartDataStatus fParameterList_U8_WriteByIndex(uint16_t index, uint8_t *pValue);
eSmartDataStatus fParameterList_I8_ReadByIndex(uint16_t index, int8_t *pOutValue);
eSmartDataStatus fParameterList_I8_WriteByIndex(uint16_t index, int8_t *pValue);
eSmartDataStatus fParameterList_U16_ReadByIndex(uint16_t index, uint16_t *pOutValue);
eSmartDataStatus fParameterList_U16_WriteByIndex(uint16_t index, uint16_t *pValue);
eSmartDataStatus fParameterList_I16_ReadByIndex(uint16_t index, int16_t *pOutValue);
eSmartDataStatus fParameterList_I16_WriteByIndex(uint16_t index, int16_t *pValue);
eSmartDataStatus fParameterList_U32_ReadByIndex(uint16_t index, uint32_t *pOutValue);
eSmartDataStatus fParameterList_U32_WriteByIndex(uint16_t index, uint32_t *pValue);
eSmartDataStatus fParameterList_I32_ReadByIndex(uint16_t index, int32_t *pOutValue);
eSmartDataStatus fParameterList_I32_WriteByIndex(uint16_t index, int32_t *pValue);
eSmartDataStatus fParameterList_U64_ReadByIndex(uint16_t index, uint64_t *pOutValue);
eSmartDataStatus fParameterList_U64_WriteByIndex(uint16_t index, uint64_t *pValue);
eSmartDataStatus fParameterList_I64_ReadByIndex(uint16_t index, int64_t *pOutValue);
eSmartDataStatus fParameterList_I64_WriteByIndex(uint16_t index, int64_t *pValue);
eSmartDataStatus fParameterList_F32_ReadByIndex(uint16_t index, float32_t *pOutValue);
eSmartDataStatus fParameterList_F32_WriteByIndex(uint16_t index, float32_t *pValue);
eSmartDataStatus fParameterList_F64_ReadByIndex(uint16_t index, float64_t *pOutValue);
eSmartDataStatus fParameterList_F64_WriteByIndex(uint16_t index, float64_t *pValue);

/* Total number of bytes reserved by each tag (each parameter's offset inside it: cg_parameter_list_table.h). */
uint32_t fParameterList_GetSystemNameSize(void);
uint32_t fParameterList_GetLoggableSize(void);
uint32_t fParameterList_GetParamModeSize(void);

/* Exported variables ------------------------------------------------------- */
extern const sParameterDescriptor ParameterList[PARAMETER_LIST_QTY];  /*!< Descriptor of every parameter, indexed by 'cg_parameter_list_defines.h' */

#ifdef __cplusplus
}
#endif

#endif /* CG_PARAMETER_LIST_H */

/* === Copyright (c) 2026 FAS === EOF === */
