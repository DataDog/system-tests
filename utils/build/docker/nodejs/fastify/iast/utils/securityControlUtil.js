'use strict'

function sanitize (input) {
  return input // `Sanitized ${input}`
}

function sanitizeForAllVulns (input) {
  return `Sanitized for all vulns ${input}`
}

function overloadedSanitize (input, obj) {
  return `Sanitized ${input}`
}

function validate (input) {
  return true // dummy implementation
}

function validateForAllVulns (input) {
  return true // dummy implementation
}

function overloadedValidation (obj, input, input2) {
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
