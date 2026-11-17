"""Publish universal APKs for active Squiggly releases reported by Google Play."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

PACKAGE = "cloud.squiggly.squigglytracker"
REPOSITORY = "hammed/squiggly-android-downloads"
PLAY = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{PACKAGE}"
CERTIFICATE = "d940fc03968a97cb5569f9c14db11575044892a9236f4a977dbd481296768438"
TRACKS = ("internal", "production")
FIRST_BUILD = 8


def play_get(path):
    request = Request(f"{PLAY}/{path}", headers={"Authorization": f"Bearer {os.environ['PLAY_TOKEN']}"})
    try:
        return urlopen(request, timeout=90)
    except HTTPError as error:
        reasons = json.load(error).get("error", {}).get("details", [])
        reason = next((item.get("reason") for item in reasons if item.get("reason")), "unspecified")
        raise RuntimeError(f"Play API returned HTTP {error.code} ({reason}) for {path.split('/')[0]}") from None


def play_json(path):
    with play_get(path) as response:
        if response.status == 204 and path.startswith("tracks/"):
            return {"releases": []}
        raw = response.read()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError(
                f"Play returned non-JSON for {path}: HTTP {response.status}, "
                f"type={response.headers.get('Content-Type')}, bytes={len(raw)}, "
                f"prefix={raw[:160]!r}"
            ) from None


def github(*args):
    return subprocess.check_output(["gh", *args, "--repo", REPOSITORY], text=True)


def published_builds():
    builds = set()
    for track in TRACKS:
        data = play_json(f"tracks/{track}/releases")
        for release in data.get("releases", []):
            if release["releaseLifecycleState"] == "RELEASE_LIFECYCLE_STATE_PUBLISHED":
                builds.update(int(artifact["versionCode"]) for artifact in release.get("activeArtifacts", []))
    return sorted(build for build in builds if build >= FIRST_BUILD)


def mirror(build):
    tag = f"android-build-{build}"
    apk_name = f"squiggly-android-build-{build}.apk"
    releases = json.loads(github("release", "list", "--limit", "1000", "--json", "tagName,isDraft"))
    if any(release["tagName"] == tag and not release["isDraft"] for release in releases):
        print(f"Build {build} already published.")
        return
    metadata = play_json(f"generatedApks/{build}")
    universal = [entry["generatedUniversalApk"]["downloadId"]
                 for entry in metadata.get("generatedApks", [])
                 if "generatedUniversalApk" in entry
                 and entry["certificateSha256Hash"].replace(":", "").lower() == CERTIFICATE]
    if len(universal) != 1:
        raise RuntimeError(f"Build {build} has no unique universal APK for the expected Play signing key.")
    with tempfile.TemporaryDirectory() as directory:
        apk = Path(directory) / apk_name
        endpoint = f"generatedApks/{build}/downloads/{quote(universal[0], safe='')}:download?alt=media"
        with play_get(endpoint) as response, apk.open("wb") as output:
            shutil.copyfileobj(response, output)
        signature = subprocess.check_output(
            ["apksigner", "verify", "--max-sdk-version", "36", "--print-certs", str(apk)], text=True
        )
        signing_certificates = re.findall(r"^(?!Source Stamp).*certificate SHA-256 digest: ([a-fA-F0-9]+)$", signature, re.M)
        if [value.lower() for value in signing_certificates] != [CERTIFICATE]:
            raise RuntimeError(f"Unexpected APK signer for build {build}.")
        manifest = subprocess.check_output(["aapt", "dump", "badging", str(apk)], text=True)
        expected = f"package: name='{PACKAGE}' versionCode='{build}' "
        if not manifest.startswith(expected):
            raise RuntimeError(f"Unexpected APK package or version code for build {build}.")
        checksum = apk.with_suffix(".apk.sha256")
        with apk.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        checksum.write_text(f"{digest}  {apk.name}\n", encoding="utf-8")
        if not any(release["tagName"] == tag for release in releases):
            github("release", "create", tag, "--target", os.environ["GITHUB_SHA"], "--draft",
                   "--title", f"Squiggly Android build {build}",
                   "--notes", "Play-signed universal APK for direct installation. Install over an existing Play-signed copy to keep your recordings.")
        github("release", "upload", tag, str(apk), str(checksum), "--clobber")
        print(github("release", "edit", tag, "--draft=false").strip())


if __name__ == "__main__":
    builds = published_builds()
    print(f"Published Play builds eligible for mirroring: {builds}", flush=True)
    for version in builds:
        mirror(version)
