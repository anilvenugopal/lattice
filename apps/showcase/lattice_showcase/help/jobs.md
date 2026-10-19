---
title: Live updates
summary: A list that refreshes itself: watch sample jobs, retry or cancel them.
order: 20
keywords: background tasks runs retry cancel failed queued running
---

The Jobs list shows background work and refreshes itself every five seconds.

## Job statuses

| Status | Meaning |
|---|---|
| Queued | Waiting for a worker |
| Running | In progress; the bar shows how far it has got |
| Succeeded | Finished without errors |
| Failed | Stopped with an error; open the job to read it |
| Cancelled | Stopped by someone before it finished |

## Retry or cancel

- **Retry** queues a failed or cancelled job again. Its attempt count goes up by one.
- **Cancel** stops a queued or running job.

Both actions apply only to jobs in those statuses. If you select a mix, the
others are skipped and the message tells you how many.

## Start a job

Choose **Run job**, give it a name and pick its type.
