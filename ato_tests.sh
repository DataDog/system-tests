echo "ATO signin/signup +identification"
./run.sh DEFAULT tests/appsec/test_automated_login_events.py::Test_V3_Login_Events

echo "ATO signin/signup +anonimization"
./run.sh APPSEC_AUTO_EVENTS_EXTENDED tests/appsec/test_automated_login_events.py::Test_V3_Login_Events_Anon

echo "ATO signin/signup +blocking"
./run.sh APPSEC_AND_RC_ENABLED tests/appsec/test_automated_login_events.py::Test_V3_Login_Events_Blocking

echo "ATO tracking +identification"
./run.sh DEFAULT tests/appsec/test_automated_user_and_session_tracking.py::Test_Automated_User_Tracking

echo "ATO tracking +blocking"
./run.sh APPSEC_AND_RC_ENABLED tests/appsec/test_automated_user_and_session_tracking.py::Test_Automated_User_Blocking
