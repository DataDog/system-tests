const { LocalStrategy } = require('passport-local')
const users = [{
  _id: 1,
  username: 'test',
  password: '1234',
  email: 'testuser@ddog.com'
}]

module.exports = function (app, passport) {
  passport.use(new LocalStrategy({ usernameField: 'username', passwordField: 'password' },
    (username, password, done) => {
      const user = users.find(user => (user.username === username) && (user.password === password))

      if (!user) {
        return done(null, false)
      } else {
        return done(null, user)
      }
    })
  )

  app.use(passport.initialize())
  app.post('/login',
    passport.authenticate('local', { session: false }),
    (req, res) => {
      res.status(200)
    }
  )
  app.post('/signup', (req, res) => {
    const user = {}
    user.username = req.body.username
    user.password = req.body.password

    if ((user.username && user.password) &&
      !(users.some(item => item.username === user.username))) {
      user._id = (() => {
        const last = users.at(-1)
        if (last && last._id) {
          return last._id + 1
        } else {
          return 1
        }
      }) ()
      res.status(200).json({ status: 'success', id: user._id, username: user.username })
    } else {
      res.status(200).json({ status: 'failure' })
    }
  })
}
