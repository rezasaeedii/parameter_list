/**
  ******************************************************************************
  * @file    parameter_descriptor.h
  * @brief   Hand written description of one parameter of the parameter list.
  *
  * This file is NOT generated; it defines the shape of the table that the code
  * generator fills in. Whenever a field is added here, the field order in
  * paramgen/src/pl_codegen/codegen/descriptor_layout.py has to be updated as well,
  * because the generated initialiser uses designated initialisers in
  * declaration order (valid in C99 and in C++20).
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
#ifndef PARAMETER_DESCRIPTOR_H
#define PARAMETER_DESCRIPTOR_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ----------------------------------------------------------------- */
#include <stdint.h>
#include <stdbool.h>

#include "smart_data.h"

/* Exported defines --------------------------------------------------------- */
/**
 * @brief Compiler independent 'weak' attribute.
 *
 */
#ifndef PARAMETER_LIST_WEAK
#   if defined(__GNUC__) || defined(__clang__) || defined(__ARMCC_VERSION)
#       define PARAMETER_LIST_WEAK  __attribute__((weak))
#   elif defined(__ICCARM__)
#       define PARAMETER_LIST_WEAK  __weak
#   else
#       define PARAMETER_LIST_WEAK
#   endif
#endif  /* PARAMETER_LIST_WEAK */

#ifndef PARAMETER_LIST_UNUSED_
#   define PARAMETER_LIST_UNUSED_(x_)   (void)(x_)
#endif  /* PARAMETER_LIST_UNUSED_ */

/* Exported macros ---------------------------------------------------------- */
/* Exported types ----------------------------------------------------------- */
/**
 * @brief
 *
 */
typedef enum {

    ePARAMETER_DESCRIPTOR_OK = 0,
    ePARAMETER_DESCRIPTOR_ERROR_NULL_REFERENCE,
    ePARAMETER_DESCRIPTOR_ERROR_WRITE

} eParameterDescriptorStatus;

/**
 * @brief What a parameter is: a monitored value, a setting, or a command.
 *
 */
typedef enum {

    ePARAMETER_TYPE_MONITORING = 0,
    ePARAMETER_TYPE_SETTING,
    ePARAMETER_TYPE_COMMAND

} eParameterType;

/**
 * @brief Full description of one parameter.
 *
 * @note  The fields must stay in this order; the generated table relies on it.
 * @note  One descriptor is exactly one value. An array declaration of N
 *        elements produces N descriptors - PosDrone[0] .. PosDrone[N-1] - each
 *        with its own index and its own log id. There is
 *        deliberately no ArraySize field: the size of the declaration is a
 *        compile time constant and lives in the generated
 *        <NAME>_ARRAY_SIZE macro, not in the table.
 *
 */
typedef struct {

    const char * pName;                         /*!< Name of the parameter, as it was written in the editor. */

    const char * pUserName;                     /*!< The name a person reads (ground station, log). Each value has its own: an element of an array or a field of a structure may differ from the rest. "" when there is none, never NULL. */

    eParameterType Type;                        /*!< What the parameter IS: monitoring, a setting, or a command. */

    void * pSmartData;                          /*!< Smart data object holding this one value. An array declaration gives one descriptor per element, each pointing at its own element. */

    uint16_t LogId;                             /*!< Identifier the logging sub-system uses for this value. Meaningful only while TagLoggable is TRUE; 0 otherwise. An array takes one consecutive id per element. */

    uint32_t TagSystemName;

    uint32_t TagResetProof;

    uint32_t TagLoggable;

    uint32_t TagLogEncryption;

    uint32_t TagParamMode;

    uint32_t Tag1;

    uint32_t Tag2;

    uint32_t Tag3;

    uint32_t Tag4;

    const char * pDescription;                  /*!< Free text description; "" when there is none, never NULL. */

} sParameterDescriptor;

/* Exported functions ------------------------------------------------------- */
eParameterDescriptorStatus fParameterDescriptor_WriteB8(const sParameterDescriptor * pParamDesc, bool_t value);
eParameterDescriptorStatus fParameterDescriptor_WriteU8(const sParameterDescriptor * pParamDesc, uint8_t value);
eParameterDescriptorStatus fParameterDescriptor_WriteI8(const sParameterDescriptor * pParamDesc, int8_t value);
eParameterDescriptorStatus fParameterDescriptor_WriteU16(const sParameterDescriptor * pParamDesc, uint16_t value);
eParameterDescriptorStatus fParameterDescriptor_WriteI16(const sParameterDescriptor * pParamDesc, int16_t value);
eParameterDescriptorStatus fParameterDescriptor_WriteU32(const sParameterDescriptor * pParamDesc, uint32_t value);
eParameterDescriptorStatus fParameterDescriptor_WriteI32(const sParameterDescriptor * pParamDesc, int32_t value);
eParameterDescriptorStatus fParameterDescriptor_WriteU64(const sParameterDescriptor * pParamDesc, uint64_t value);
eParameterDescriptorStatus fParameterDescriptor_WriteI64(const sParameterDescriptor * pParamDesc, int64_t value);
eParameterDescriptorStatus fParameterDescriptor_WriteF32(const sParameterDescriptor * pParamDesc, float32_t value);
eParameterDescriptorStatus fParameterDescriptor_WriteF64(const sParameterDescriptor * pParamDesc, float64_t value);

void fParameterDescriptor_ParameterWriteCompletedCallback(const sParameterDescriptor *sender, void *pEv);

/* Exported variables ------------------------------------------------------- */

#ifdef __cplusplus
}
#endif

#endif /* PARAMETER_DESCRIPTOR_H */

/* === Copyright (c) 2026 FAS === EOF === */
