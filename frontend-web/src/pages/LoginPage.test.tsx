import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import { LoginPage } from '../pages/LoginPage'

vi.mock('../api/pharmacy', () => ({
  login: vi.fn(),
  fetchMe: vi.fn(),
  refreshSession: vi.fn(),
  logoutSession: vi.fn(),
}))

import { login as apiLogin, logoutSession, refreshSession } from '../api/pharmacy'

describe('LoginPage', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(apiLogin).mockReset()
    vi.mocked(refreshSession).mockReset()
    vi.mocked(refreshSession).mockRejectedValue(new Error('no session'))
    vi.mocked(logoutSession).mockReset()
    vi.mocked(logoutSession).mockResolvedValue(undefined)
  })

  it('submits credentials to login API', async () => {
    const user = userEvent.setup()
    vi.mocked(apiLogin).mockResolvedValue({
      access_token: 'tok',
      token_type: 'bearer',
      user: {
        id: 1,
        email: 'admin@test.com',
        role: 'admin',
        is_active: true,
        created_at: '2026-01-01T00:00:00',
      },
    })

    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>,
    )

    await user.type(await screen.findByLabelText(/email/i), 'admin@test.com')
    await user.type(screen.getByLabelText(/password/i), 'adminpass1')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(apiLogin).toHaveBeenCalledWith('admin@test.com', 'adminpass1')
  })
})
