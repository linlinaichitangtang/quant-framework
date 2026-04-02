/**
 * OpenClaw 量化交易平台 JavaScript SDK - 自定义异常
 */

class OpenClawError extends Error {
  /**
   * @param {string} message - 错误消息
   * @param {number} [code] - 错误码
   * @param {object} [details] - 错误详情
   */
  constructor(message, code = null, details = {}) {
    super(message)
    this.name = 'OpenClawError'
    this.code = code
    this.details = details
  }

  toString() {
    return this.code ? `[${this.code}] ${this.message}` : this.message
  }
}

class AuthenticationError extends OpenClawError {
  constructor(message = '认证失败，请检查 API Key 和 Secret', details) {
    super(message, 401, details)
    this.name = 'AuthenticationError'
  }
}

class RateLimitError extends OpenClawError {
  /**
   * @param {string} [message] - 错误消息
   * @param {number} [retryAfter] - 重试等待秒数
   */
  constructor(message = '请求频率超限，请稍后重试', retryAfter = null) {
    super(message, 429, { retryAfter })
    this.name = 'RateLimitError'
    this.retryAfter = retryAfter
  }
}

class APIError extends OpenClawError {
  /**
   * @param {string} [message] - 错误消息
   * @param {number} [statusCode] - HTTP 状态码
   */
  constructor(message = 'API 请求错误', statusCode = null) {
    super(message, statusCode, {})
    this.name = 'APIError'
    this.statusCode = statusCode
  }
}

class ConnectionError extends OpenClawError {
  constructor(message = '无法连接到 OpenClaw 服务') {
    super(message, 0, {})
    this.name = 'ConnectionError'
  }
}

module.exports = {
  OpenClawError,
  AuthenticationError,
  RateLimitError,
  APIError,
  ConnectionError,
}
