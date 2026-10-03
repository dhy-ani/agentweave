# 0005. Drive the swipe animation with CSS and a timer

Status: Accepted

## Context
The swipe card used react-spring 10.0.1 and reported the swipe in the spring's `onRest` callback. Unit tests passed because they set `skipAnimation`. Driving the real app in headless Chrome with Playwright showed the spring never animated with React 19.1: the card's transform stayed `none`, `onRest` never fired, and no pass, like or save was ever recorded, whether by button or by drag.

## Decision
Keep `@use-gesture/react` for drag tracking. Render the card position with a CSS `transform` (`cardTransform` in `frontend/src/lib/swipe.js`) and a CSS transition. Fire the swipe outcome from a timer (`SWIPE_OUT_MS`, 280 ms), so it never depends on an animation running. Remove react-spring.

## Consequences
- Swipes register deterministically, including with `prefers-reduced-motion` (transition disabled) and in background tabs where animation frames are paused.
- The card transform is a pure, unit-tested function.
- Lesson recorded in the testing guide: component tests that disable animation need at least one real-browser check of the same flow.
