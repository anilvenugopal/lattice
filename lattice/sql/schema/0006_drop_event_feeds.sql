-- The event-feed reader is removed (ADR 0012): another process's state is read from its
-- views on a timer, not streamed from a cursor.

DROP TABLE lattice.event_feed;
