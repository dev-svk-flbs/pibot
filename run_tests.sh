#!/bin/bash
# Test Suite Runner for Phase 1

echo "=========================================="
echo "JARVIS Phase 1 Test Suite"
echo "=========================================="
echo ""

cd /home/saptapi/robot
source venv/bin/activate

# Test 1: MQTT Broker
echo "Running Test 1: MQTT Broker Connectivity"
echo "------------------------------------------"
python test_mqtt.py
TEST1_RESULT=$?
echo ""

if [ $TEST1_RESULT -ne 0 ]; then
    echo "❌ MQTT broker test failed. Fix this before continuing."
    exit 1
fi

# Test 2 & 3 require Session Manager to be running
echo "=========================================="
echo "Tests 2 and 3 require Session Manager"
echo "=========================================="
echo ""
echo "Please open a NEW terminal and run:"
echo "  cd /home/saptapi/robot"
echo "  source venv/bin/activate"
echo "  python modules/session_manager.py"
echo ""
read -p "Press Enter when Session Manager is running..."

# Test 2: State Transitions
echo ""
echo "Running Test 2: State Transitions"
echo "------------------------------------------"
python test_session.py
TEST2_RESULT=$?
echo ""

# Test 3: Timeout
echo ""
echo "Running Test 3: Session Timeout (this takes 35 seconds)"
echo "------------------------------------------"
python test_timeout.py
TEST3_RESULT=$?
echo ""

# Summary
echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
echo "Test 1 (MQTT Broker):       $([ $TEST1_RESULT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo "Test 2 (State Transitions): $([ $TEST2_RESULT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo "Test 3 (Timeout):           $([ $TEST3_RESULT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
echo ""

if [ $TEST1_RESULT -eq 0 ] && [ $TEST2_RESULT -eq 0 ] && [ $TEST3_RESULT -eq 0 ]; then
    echo "✅ ALL TESTS PASSED - Phase 1 is working!"
    exit 0
else
    echo "❌ SOME TESTS FAILED - Review output above"
    exit 1
fi
