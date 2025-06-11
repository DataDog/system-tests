const AWS_HOST = process.env.SYSTEM_TESTS_AWS_URL ?? 'https://sns.us-east-1.amazonaws.com'
const AWS_ACCT = process.env.SYSTEM_TESTS_AWS_URL ? '000000000000' : '601427279990'

module.exports = { AWS_HOST, AWS_ACCT }
