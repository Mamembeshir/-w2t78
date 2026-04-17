/**
 * Tests for the pure helper functions exported from api.ts.
 * The Axios instance and interceptors are not tested here — they
 * require a real or mock HTTP server and belong in integration tests.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setTokens, clearTokens, hasToken } from '@/lib/api'

beforeEach(() => {
  localStorage.clear()
})

describe('setTokens', () => {
  it('persists the access token in localStorage', () => {
    setTokens('access-abc', 'refresh-xyz')
    expect(localStorage.getItem('access_token')).toBe('access-abc')
  })

  it('persists the refresh token in localStorage', () => {
    setTokens('access-abc', 'refresh-xyz')
    expect(localStorage.getItem('refresh_token')).toBe('refresh-xyz')
  })

  it('overwrites an existing access token', () => {
    setTokens('first', 'r1')
    setTokens('second', 'r2')
    expect(localStorage.getItem('access_token')).toBe('second')
  })
})

describe('clearTokens', () => {
  it('removes the access token', () => {
    setTokens('a', 'r')
    clearTokens()
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('removes the refresh token', () => {
    setTokens('a', 'r')
    clearTokens()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })

  it('is a no-op when tokens are already absent', () => {
    expect(() => clearTokens()).not.toThrow()
  })
})

describe('hasToken', () => {
  it('returns false when no token is stored', () => {
    expect(hasToken()).toBe(false)
  })

  it('returns true after setTokens is called', () => {
    setTokens('tok', 'ref')
    expect(hasToken()).toBe(true)
  })

  it('returns false after clearTokens is called', () => {
    setTokens('tok', 'ref')
    clearTokens()
    expect(hasToken()).toBe(false)
  })
})
