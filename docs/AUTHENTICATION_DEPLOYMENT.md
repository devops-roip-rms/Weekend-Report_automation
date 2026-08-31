# Weekend Report Authentication And Deployment Modes

## Overview

Weekend Report supports two mutually exclusive production authentication modes.

The same application image supports both modes.

A deployment selects one mode at runtime.

---

## Mode A - Direct HTTPS Access

Flow:

```text
Browser
  |
  | HTTPS :8080
  v
Weekend Report
  |
  +-- local_login
      |
      +-- local password hashes
      +-- signed secure session cookie