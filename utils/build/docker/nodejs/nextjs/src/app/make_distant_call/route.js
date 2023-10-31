import { NextResponse } from 'next/server'
import axios from 'axios'

export async function GET (request) {
  const url = request.nextUrl.searchParams.get('url')

  try {
    const response = await axios.get(url)

    return NextResponse.json({
      url,
      status_code: response.statusCode,
      request_headers: null,
      response_headers: null
    })
  } catch (error) {
    return NextResponse.json({
      url,
      status_code: 500,
      request_headers: null,
      response_headers: null
    })
  }
}
