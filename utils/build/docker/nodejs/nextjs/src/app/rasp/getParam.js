/**
 * Reads a parameter the way the Express weblog reads req.query and req.body: from the query string of a GET request,
 * or from the JSON or url-encoded body of other requests.
 * @param {import('next/server').NextRequest} request
 * @param {string} name
 */
export async function getParam (request, name) {
  if (request.method === 'GET') return request.nextUrl.searchParams.get(name)

  const contentType = request.headers.get('content-type') || ''
  if (contentType.includes('application/json')) return (await request.json())[name]
  if (contentType.includes('application/x-www-form-urlencoded')) return (await request.formData()).get(name)
}
