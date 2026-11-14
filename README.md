# Squiggly for Android

Find installable Android APKs under [Releases](https://github.com/hammed/squiggly-android-downloads/releases).

Install the APK over your existing Play-signed installation to preserve local recordings and Blackboxes.

## How releases appear here

The **Mirror published Google Play APKs** workflow checks the Squiggly internal
and production tracks every 30 minutes. You can also run it from the Actions
tab after publishing. It copies Play's signed universal APK and publishes a
SHA-256 checksum. Build 8 is the first build mirrored.

The workflow uses short-lived Google credentials. Its identity provider is set
in the `PLAY_WORKLOAD_IDENTITY_PROVIDER` repository variable. Google Cloud grants
impersonation of the Squiggly APK Downloads service account to this repository's
mirror workflow on `main`. The service account's Play grant is scoped to Squiggly.
GitHub's workflow token publishes releases in this repository.

If a run fails, check its Actions log and rerun it after the problem is resolved.
An interrupted upload leaves a draft that the next run can finish. Disable
the workflow in Actions to pause mirroring.

Users can verify a downloaded file with `sha256sum -c *.apk.sha256` from the
download directory. Android verifies the APK signing certificate at install.
