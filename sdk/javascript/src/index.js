/**
 * OpenClaw 量化交易平台 JavaScript SDK
 *
 * @module openclaw-sdk
 * @version 2.0.0
 */

const { OpenClawClient } = require('./client')

const {
  OpenClawError,
  AuthenticationError,
  RateLimitError,
  APIError,
  ConnectionError,
} = require('./exceptions')

module.exports = {
  OpenClawClient,
  OpenClawError,
  AuthenticationError,
  RateLimitError,
  APIError,
  ConnectionError,
}

module.exports.default = OpenClawClient
module.exports.OpenClawClient = OpenClawClient
