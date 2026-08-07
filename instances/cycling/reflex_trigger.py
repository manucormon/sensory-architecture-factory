"""
Cycling instance — reflex trigger.

HAS_REFLEX = False.

The real ride data (GoldenCheetah OpenData) has no crash labels — no peloton
incident data, no accelerometer spikes, no video-based detection. Inventing a
proxy crash signal from speed drops or power spikes would be DECLARED data
dressed as PROXY, which violates the labeling contract.

Honest position: this instance cannot detect crashes. The governance engine
still operates correctly for the other four channels. A future instance with
real incident data (team radio logs, race commissaire reports, accelerometer
streams) could set HAS_REFLEX = True and derive crash_signal as PROXY.

If a reflex is needed in production, the data slot is here — wire a real
source to it rather than approximating with the power signal.
"""

HAS_REFLEX = False
