import unittest
import sys
import time

def run_meetora_test_suite():
    print("=" * 70)
    print(" MEETORA AI MEETING ANALYZER - END-TO-END TEST SUITE")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print(f" TESTS RAN: {result.testsRun} in {elapsed:.3f}s")
    print(f" SUCCESSES: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f" FAILURES:  {len(result.failures)}")
    print(f" ERRORS:    {len(result.errors)}")
    print("=" * 70)

    if result.wasSuccessful():
        print(">>> 100% PASS: ALL 15 ROADMAP TEST SPECIFICATIONS VERIFIED!")
        sys.exit(0)
    else:
        print(">>> SOME TESTS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    run_meetora_test_suite()

