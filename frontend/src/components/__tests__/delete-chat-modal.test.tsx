/**
 * DeleteChatModal focus management tests
 */

import React, { useState } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { DeleteChatModal } from '../chat/delete-chat-modal'

function Harness() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button onClick={() => setOpen(true)}>Open</button>
      <button>Behind the overlay</button>
      <DeleteChatModal
        isOpen={open}
        onClose={() => setOpen(false)}
        onConfirm={() => {}}
        chatTitle="Calculus study plan"
      />
    </>
  )
}

describe('DeleteChatModal', () => {
  it('moves focus into the dialog when it opens', () => {
    render(<Harness />)
    const opener = screen.getByText('Open')
    opener.focus()
    fireEvent.click(opener)

    expect(screen.getByRole('alertdialog')).toHaveFocus()
  })

  it('keeps Tab and Shift+Tab inside the dialog', () => {
    render(<Harness />)
    fireEvent.click(screen.getByText('Open'))
    const cancel = screen.getByRole('button', { name: 'Cancel' })
    const confirm = screen.getByRole('button', { name: 'Delete chat' })

    confirm.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(cancel).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(confirm).toHaveFocus()
  })

  it('returns focus to the opener when it closes', () => {
    render(<Harness />)
    const opener = screen.getByText('Open')
    opener.focus()
    fireEvent.click(opener)

    fireEvent.keyDown(document, { key: 'Escape' })

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })
})
