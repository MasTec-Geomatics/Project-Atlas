# 0005. Potree for Point Clouds

**Status:** Accepted

**Date:** 2026-11-02

## Context

The web app needs to display LiDAR point clouds for each project in the browser.

## Decision

Use Potree to display point clouds in the web app.

## Consequences

- LiDAR files need a viewing copy prepared for Potree. The original files stay untouched.
- The viewing format is not yet decided.
- Potree is wrapped in a Vue component.
