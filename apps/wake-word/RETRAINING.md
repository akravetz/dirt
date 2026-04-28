# Wake-Word Retraining Workflow

Read before building a trainer image, kicking off a RunPod training job, or deploying a new model. The numbered chain in `apps/wake-word/CLAUDE.md` is the summary; this file is the actual command sequence with explanation.

```bash
# 1. (Optional, infrequent) refresh data:
uv run python apps/wake-word/data-gen/elevenlabs-clones-batch.py
uv run python apps/wake-word/data-gen/elevenlabs-neighbors-batch.py
# RIR capture is two-machine — see capture-rir-record.py docstring.

# 2. (One-time per dataset bump) push fresh data into the Network Volume:
scripts/wakeword-volume-bump dirt-wakeword-mine ./staged/mine \
    --notes "added 200 realmic positives from <session>"
# Direct S3 upload to the volume; recomputes content hash; rewrites
# MANIFEST.json. The volume IS the source of truth — content_hash is
# what shows up in the next run's wandb.config + run-manifest.json.

# 3. Build + push trainer image (only if Dockerfile or src/ changed):
scripts/runpod-build-image
# Builds linux/amd64, smoke-tests, pushes to ghcr.io/<owner>/dirt-wake-word-trainer.

# 4. Trigger a training run:
scripts/runpod-train
# POST training pod → poll API for desiredStatus=EXITED → S3-download
# out/<pod_id>/ → DELETE pod. Artifacts land at
# var/wake-word/models/<date>-<pod_id>/. ~30-60 min on a 4090, ~$0.40-0.70.

# 5. Validate the new model offline:
uv run python scripts/validate-wake-model.py \
    var/wake-word/models/<datestamp>/hey_claudia.onnx
# Compare recall/precision against var/wake-word/models/current/.

# 6. (Optional) live-test through the Jabra:
systemctl --user stop dirt-voice
uv run python apps/wake-word/validation/live-test.py \
    var/wake-word/models/<datestamp>/hey_claudia.onnx
# (speak; Ctrl-C; restart service)

# 7. **REQUIRED — log the experiment.** Append a new entry to
#    `wiki/wake-word-experiments.md` for EVERY trained model, deployed or not.
#    Use the most recent entry as a template (vN, status, commit, image digest,
#    W&B run, pod id, wall, what changed, training data, training config,
#    validation results table, per-phase wall, operational notes). If you
#    deploy, also flip the previous deployed entry's `**Status:**` to `superseded`.
#    Skipping this step means the next agent has to dig through git/W&B/S3 to
#    reconstruct what was run and why — don't make them.

# 8. Deploy if validation looks good:
ln -sfn <datestamp>-runpod var/wake-word/models/current
systemctl --user restart dirt-voice
```

## Notes

- The container ALWAYS exits 0 (entrypoint catches BaseException, writes FAILURE sentinel, returns). Communicate failure via the sentinel under `out/<run_id>/`, never via exit status.
- Don't reach for SSH/SCP for moving files between local and the volume. Use the S3-compatible API (`s3api-<dc>.runpod.io/`) — `wakeword-volume-bump`, `wakeword-volume-snapshot`, and `runpod-train`'s artifact pull all use it.
- See `apps/wake-word/CLAUDE.md` "Critical gotchas" for the full hazards list.
