/**
 * API Client Tests
 */

import { apiRequest, APIError, NetworkError, AuthenticationError } from '../api-client'

describe('API Client', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(global.fetch as jest.Mock).mockClear()
  })

  describe('apiRequest', () => {
    it('should make successful request', async () => {
      const mockData = { data: 'test' }
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockData,
        headers: new Headers({ 'content-type': 'application/json' }),
      })

      const result = await apiRequest('https://api.test.com/data')
      expect(result).toEqual(mockData)
    })

    it('should handle 401 authentication errors', async () => {
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Unauthorized' }),
      })

      await expect(apiRequest('https://api.test.com/data')).rejects.toThrow(
        AuthenticationError
      )
    })

    it('should retry on network errors', async () => {
      ;(global.fetch as jest.Mock)
        .mockRejectedValueOnce(new TypeError('Network error'))
        .mockRejectedValueOnce(new TypeError('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: 'success' }),
          headers: new Headers({ 'content-type': 'application/json' }),
        })

      const result = await apiRequest('https://api.test.com/data', {
        retryOptions: { maxRetries: 3, retryDelay: 10 },
      })

      expect(result).toEqual({ data: 'success' })
      expect(global.fetch).toHaveBeenCalledTimes(3)
    })

    it('should retry on 5xx errors', async () => {
      ;(global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: false,
          status: 503,
          json: async () => ({ detail: 'Service unavailable' }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: 'success' }),
          headers: new Headers({ 'content-type': 'application/json' }),
        })

      const result = await apiRequest('https://api.test.com/data', {
        retryOptions: { maxRetries: 3, retryDelay: 10 },
      })

      expect(result).toEqual({ data: 'success' })
      expect(global.fetch).toHaveBeenCalledTimes(2)
    })

    it('should not retry on 4xx errors', async () => {
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'Bad request' }),
      })

      await expect(apiRequest('https://api.test.com/data')).rejects.toThrow()
      expect(global.fetch).toHaveBeenCalledTimes(1)
    })
  })
})
