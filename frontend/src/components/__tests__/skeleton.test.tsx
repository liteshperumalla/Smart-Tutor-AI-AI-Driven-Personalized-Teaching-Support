/**
 * Skeleton loading placeholder tests
 */

import React from 'react'
import { render, screen } from '@testing-library/react'
import { SkeletonRegion, SkeletonTable, SkeletonText } from '../skeleton'

describe('Skeleton', () => {
  it('announces the loading state once per region', () => {
    render(
      <SkeletonRegion label="Loading users">
        <SkeletonTable rows={3} columns={3} />
      </SkeletonRegion>
    )

    const region = screen.getByRole('status')
    expect(region).toHaveAttribute('aria-busy', 'true')
    expect(region).toHaveTextContent('Loading users…')
  })

  it('hides placeholder blocks from assistive tech', () => {
    const { container } = render(<SkeletonText lines={4} />)

    const lines = container.querySelectorAll('.shimmer-line')
    expect(lines).toHaveLength(4)
    lines.forEach((line) => expect(line).toHaveAttribute('aria-hidden', 'true'))
  })
})
