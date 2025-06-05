/* eslint-disable no-undef */

import { NextResponse } from 'next/server'

export async function GET () {

  return new NextResponse('OK', {
    status: 200,
    headers: {
      'Content-Type': 'text/plain',
    },
  });
}
