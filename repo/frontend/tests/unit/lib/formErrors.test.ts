import { describe, it, expect } from 'vitest'
import { extractFieldErrors, extractMessage } from '@/lib/formErrors'

// ─── extractFieldErrors ────────────────────────────────────────────────────

describe('extractFieldErrors', () => {
  it('returns empty object when err is null', () => {
    expect(extractFieldErrors(null)).toEqual({})
  })

  it('returns empty object when err has no response', () => {
    expect(extractFieldErrors(new Error('oops'))).toEqual({})
  })

  it('returns empty object when response.data has no details', () => {
    const err = { response: { data: { message: 'Bad request' } } }
    expect(extractFieldErrors(err)).toEqual({})
  })

  it('extracts single-string detail values', () => {
    const err = {
      response: {
        data: {
          details: { quantity: 'Ensure this value is positive.', reference: 'Required.' },
        },
      },
    }
    expect(extractFieldErrors(err)).toEqual({
      quantity: 'Ensure this value is positive.',
      reference: 'Required.',
    })
  })

  it('takes only the first message when detail value is an array', () => {
    const err = {
      response: {
        data: {
          details: { unit_cost: ['This field is required.', 'Must be a number.'] },
        },
      },
    }
    expect(extractFieldErrors(err)).toEqual({ unit_cost: 'This field is required.' })
  })

  it('coerces non-string detail values with String()', () => {
    const err = {
      response: { data: { details: { quantity: 42 as unknown as string } } },
    }
    expect(extractFieldErrors(err)).toEqual({ quantity: '42' })
  })

  it('handles an empty details object', () => {
    const err = { response: { data: { details: {} } } }
    expect(extractFieldErrors(err)).toEqual({})
  })
})

// ─── extractMessage ────────────────────────────────────────────────────────

describe('extractMessage', () => {
  it('returns the fallback when err is null', () => {
    expect(extractMessage(null, 'Fallback.')).toBe('Fallback.')
  })

  it('uses the default fallback when none supplied', () => {
    expect(extractMessage(null)).toBe('An error occurred.')
  })

  it('returns response.data.message when present', () => {
    const err = { response: { data: { message: 'Insufficient stock.' } } }
    expect(extractMessage(err, 'Fallback.')).toBe('Insufficient stock.')
  })

  it('returns fallback when response.data.message is missing', () => {
    const err = { response: { data: { details: { qty: 'bad' } } } }
    expect(extractMessage(err, 'Default error.')).toBe('Default error.')
  })

  it('returns fallback when response is missing', () => {
    expect(extractMessage({ code: 'NETWORK_ERROR' }, 'Net error.')).toBe('Net error.')
  })
})
