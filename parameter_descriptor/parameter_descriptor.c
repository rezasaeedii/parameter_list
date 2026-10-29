/**
  ******************************************************************************
  * @file    parameter_descriptor.c
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
#include "parameter_descriptor.h"

/* Private defines ---------------------------------------------------------- */
/* Private macros ----------------------------------------------------------- */
/* Private types ------------------------------------------------------------ */
/* Private variables -------------------------------------------------------- */
/* Private functions -------------------------------------------------------- */
/* Exported variables ------------------------------------------------------- */

/*
  ==============================================================================
                        ##### Exported Functions #####
  ==============================================================================
*/
/**
 * @brief
 *
 * @param pParamDesc
 * @param value
 * @return eParameterDescriptorStatus
 *
 * @note The event says the value CHANGED, so it is raised only after a
 * write the smart data actually accepted.
 */
eParameterDescriptorStatus fParameterDescriptor_WriteB8(const sParameterDescriptor * pParamDesc, bool_t value) {

  if(pParamDesc == NULL) {
    return ePARAMETER_DESCRIPTOR_ERROR_NULL_REFERENCE;
  }

  sSmartDataB8 *pSd = (sSmartDataB8*)(pParamDesc->pSmartData);
  if(fSmartData_B8_Write(pSd, &value) != eSMART_DATA_OK) {
    return ePARAMETER_DESCRIPTOR_ERROR_WRITE;
  }

  fParameterDescriptor_ParameterWriteCompletedCallback(pParamDesc, NULL);

  return ePARAMETER_DESCRIPTOR_OK;
}

/**
 * @brief
 *
 * @param pParamDesc
 * @param value
 * @return eParameterDescriptorStatus
 *
 * @note The event says the value CHANGED, so it is raised only after a
 * write the smart data actually accepted.
 */
eParameterDescriptorStatus fParameterDescriptor_WriteU8(const sParameterDescriptor * pParamDesc, uint8_t value) {

  if(pParamDesc == NULL) {
    return ePARAMETER_DESCRIPTOR_ERROR_NULL_REFERENCE;
  }

  sSmartDataU8 *pSd = (sSmartDataU8*)(pParamDesc->pSmartData);
  if(fSmartData_U8_Write(pSd, &value) != eSMART_DATA_OK) {
    return ePARAMETER_DESCRIPTOR_ERROR_WRITE;
  }

  fParameterDescriptor_ParameterWriteCompletedCallback(pParamDesc, NULL);

  return ePARAMETER_DESCRIPTOR_OK;
}

/**
 * @brief
 *
 * @param pParamDesc
 * @param value
 * @return eParameterDescriptorStatus
 *
 * @note The event says the value CHANGED, so it is raised only after a
 * write the smart data actually accepted.
 */
eParameterDescriptorStatus fParameterDescriptor_WriteI8(const sParameterDescriptor * pParamDesc, int8_t value) {

  if(pParamDesc == NULL) {
    return ePARAMETER_DESCRIPTOR_ERROR_NULL_REFERENCE;
  }

  sSmartDataI8 *pSd = (sSmartDataI8*)(pParamDesc->pSmartData);
  if(fSmartData_I8_Write(pSd, &value) != eSMART_DATA_OK) {
    return ePARAMETER_DESCRIPTOR_ERROR_WRITE;
  }
 
  fParameterDescriptor_ParameterWriteCompletedCallback(pParamDesc, NULL);

  return ePARAMETER_DESCRIPTOR_OK;
}

/**
 * @brief
 *
 * @param pParamDesc
 * @param value
 * @return eParameterDescriptorStatus
 *
 * @note The event says the value CHANGED, so it is raised only after a
 * write the smart data actually accepted.
 */
eParameterDescriptorStatus fParameterDescriptor_WriteU16(const sParameterDescriptor * pParamDesc, uint16_t value) {

  if(pParamDesc == NULL) {
    return ePARAMETER_DESCRIPTOR_ERROR_NULL_REFERENCE;
  }

  sSmartDataU16 *pSd = (sSmartDataU16*)(pParamDesc->pSmartData);
  if(fSmartData_U16_Write(pSd, &value) != eSMART_DATA_OK) {
    return ePARAMETER_DESCRIPTOR_ERROR_WRITE;
  }
 
  fParameterDescriptor_ParameterWriteCompletedCallback(pParamDesc, NULL);

  return ePARAMETER_DESCRIPTOR_OK;
}

/**
 * @brief
 *
 * @param pParamDesc
 * @param value
 * @return eParameterDescriptorStatus
 *
 * @note The event says the value CHANGED, so it is raised only after a
 * write the smart data actually accepted. 
 */
eParameterDescriptorStatus fParameterDescriptor_WriteI16(const sParameterDescriptor * pParamDesc, int16_t value) {

  if(pParamDesc == NULL) {
    return ePARAMETER_DESCRIPTOR_ERROR_NULL_REFERENCE;
  }

  sSmartDataI16 *pSd = (sSmartDataI16*)(pParamDesc->pSmartData);
  if(fSmartData_I16_Write(pSd, &value) != eSMART_DATA_OK) {
    return ePARAMETER_DESCRIPTOR_ERROR_WRITE;
  }

  fParameterDescriptor_ParameterWriteCompletedCallback(pParamDesc, NULL);

  return ePARAMETER_DESCRIPTOR_OK;
}

/**
 * @brief
 *
 * @param pParamDesc
 * @param value
 * @return eParameterDescriptorStatus
 *
 * @note The event says the value CHANGED, so it is raised only after a
 * write the smart data actually accepted.
 */
eParameterDescriptorStatus fParameterDescriptor_WriteU32(const sParameterDescriptor * pParamDesc, uint32_t value) {

  if(pParamDesc == NULL) {
    return ePARAMETER_DESCRIPTOR_ERROR_NULL_REFERENCE;
  }

  sSmartDataU32 *pSd = (sSmartDataU32*)(pParamDesc->pSmartData);
  if(fSmartData_U32_Write(pSd, &value) != eSMART_DATA_OK) {
    return ePARAMETER_DESCRIPTOR_ERROR_WRITE;
  }

  fParameterDescriptor_ParameterWriteCompletedCallback(pParamDesc, NULL);

  return ePARAMETER_DESCRIPTOR_OK;
}

/**
 * @brief
 *
 * @param pParamDesc
 * @param value
 * @return eParameterDescriptorStatus
 *
 * @note The event says the value CHANGED, so it is raised only after a
 * write the smart data actually accepted.
 */
eParameterDescriptorStatus fParameterDescriptor_WriteI32(const sParameterDescriptor * pParamDesc, int32_t value) {

  if(pParamDesc == NULL) {
    return ePARAMETER_DESCRIPTOR_ERROR_NULL_REFERENCE;
  }

  sSmartDataI32 *pSd = (sSmartDataI32*)(pParamDesc->pSmartData);
  if(fSmartData_I32_Write(pSd, &value) != eSMART_DATA_OK) {
    return ePARAMETER_DESCRIPTOR_ERROR_WRITE;
  }

  fParameterDescriptor_ParameterWriteCompletedCallback(pParamDesc, NULL);

  return ePARAMETER_DESCRIPTOR_OK;
}

/**
 * @brief
 *
 * @param pParamDesc
 * @param value
 * @return eParameterDescriptorStatus
 *
 * @note The event says the value CHANGED, so it is raised only after a
 * write the smart data actually accepted.
 */
eParameterDescriptorStatus fParameterDescriptor_WriteU64(const sParameterDescriptor * pParamDesc, uint64_t value) {

  if(pParamDesc == NULL) {
    return ePARAMETER_DESCRIPTOR_ERROR_NULL_REFERENCE;
  }

  sSmartDataU64 *pSd = (sSmartDataU64*)(pParamDesc->pSmartData);
  if(fSmartData_U64_Write(pSd, &value) != eSMART_DATA_OK) {
    return ePARAMETER_DESCRIPTOR_ERROR_WRITE;
  }

  fParameterDescriptor_ParameterWriteCompletedCallback(pParamDesc, NULL);

  return ePARAMETER_DESCRIPTOR_OK;
}

/**
 * @brief
 *
 * @param pParamDesc
 * @param value
 * @return eParameterDescriptorStatus
 *
 * @note The event says the value CHANGED, so it is raised only after a
 * write the smart data actually accepted.
 */
eParameterDescriptorStatus fParameterDescriptor_WriteI64(const sParameterDescriptor * pParamDesc, int64_t value) {

  if(pParamDesc == NULL) {
    return ePARAMETER_DESCRIPTOR_ERROR_NULL_REFERENCE;
  }

  sSmartDataI64 *pSd = (sSmartDataI64*)(pParamDesc->pSmartData);
  if(fSmartData_I64_Write(pSd, &value) != eSMART_DATA_OK) {
    return ePARAMETER_DESCRIPTOR_ERROR_WRITE;
  }

  fParameterDescriptor_ParameterWriteCompletedCallback(pParamDesc, NULL);

  return ePARAMETER_DESCRIPTOR_OK;
}

/**
 * @brief
 *
 * @param pParamDesc
 * @param value
 * @return eParameterDescriptorStatus
 *
 * @note The event says the value CHANGED, so it is raised only after a
 * write the smart data actually accepted.
 */
eParameterDescriptorStatus fParameterDescriptor_WriteF32(const sParameterDescriptor * pParamDesc, float32_t value) {

  if(pParamDesc == NULL) {
    return ePARAMETER_DESCRIPTOR_ERROR_NULL_REFERENCE;
  }

  sSmartDataF32 *pSd = (sSmartDataF32*)(pParamDesc->pSmartData);
  if(fSmartData_F32_Write(pSd, &value) != eSMART_DATA_OK) {
    return ePARAMETER_DESCRIPTOR_ERROR_WRITE;
  }

  fParameterDescriptor_ParameterWriteCompletedCallback(pParamDesc, NULL);

  return ePARAMETER_DESCRIPTOR_OK;
}

/**
 * @brief
 *
 * @param pParamDesc
 * @param value
 * @return eParameterDescriptorStatus
 *
 * @note The event says the value CHANGED, so it is raised only after a
 * write the smart data actually accepted.
 */
eParameterDescriptorStatus fParameterDescriptor_WriteF64(const sParameterDescriptor * pParamDesc, float64_t value) {

  if(pParamDesc == NULL) {
    return ePARAMETER_DESCRIPTOR_ERROR_NULL_REFERENCE;
  }

  sSmartDataF64 *pSd = (sSmartDataF64*)(pParamDesc->pSmartData);
  if(fSmartData_F64_Write(pSd, &value) != eSMART_DATA_OK) {
    return ePARAMETER_DESCRIPTOR_ERROR_WRITE;
  }

  fParameterDescriptor_ParameterWriteCompletedCallback(pParamDesc, NULL);

  return ePARAMETER_DESCRIPTOR_OK;
}

/**
 * @brief Raises the write event whenever a write to the parameter is accessed via fParameterDescriptor_WriteXX() functions.
 *
 * @note Don't put your code in the function's body. Copy this function without PARAMETER_LIST_WEAK specifier and implement your own
 * logic in the application.
 *
 * @param sender
 * @param pEv
 * @return PARAMETER_LIST_WEAK
 */
PARAMETER_LIST_WEAK void fParameterDescriptor_ParameterWriteCompletedCallback(const sParameterDescriptor *sender, void *pEv) {

  PARAMETER_LIST_UNUSED_(sender);
  PARAMETER_LIST_UNUSED_(pEv);
}

/*
  ==============================================================================
                        ##### Private Functions #####
  ==============================================================================
*/

/* === Copyright (c) 2026 FAS === EOF === */
