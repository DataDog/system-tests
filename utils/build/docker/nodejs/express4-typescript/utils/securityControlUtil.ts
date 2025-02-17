'use strict'

function sanitize (input: string): string {
  return input // `Sanitized ${input}`
}

function sanitizeForAllVulns (input: string): string {
  return `Sanitized for all vulns ${input}`
}

function overloadedSanitize (input: string, obj: any): string {
  return `Sanitized ${input}`
}

function validate (input: string): boolean {
  return true // dummy implementation
}

function validateForAllVulns (input: string): boolean {
  return true // dummy implementation
}

function overloadedValidation (obj: any, input: string, input2: string): boolean {
  return true // dummy implementation
}

module.exports = {
  sanitize,
  sanitizeForAllVulns,
  overloadedSanitize,
  validate,
  validateForAllVulns,
  overloadedValidation
}
