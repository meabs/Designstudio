"""Imported first by unittest discovery (alphabetical). Tests must never start real coding agents: without this flag the studio
seeds its runners from whatever agents are installed on the machine, and a full run once exhausted the host's memory."""
import os
os.environ.setdefault('STUDIO_SEED_FIXTURES', '1')
