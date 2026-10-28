# Sourced as: source "$ROOT_DIR/scripts/require-branch.sh" <branch>
# Each folder (scripts/dev, scripts/dev2, scripts/prod) belongs to one branch.
# Deploys copy the local working tree to production, so running a script on
# the wrong branch would ship or run code that doesn't belong there.
REQUIRED_BRANCH="$1"
BRANCH="$(git -C "$ROOT_DIR" rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "$REQUIRED_BRANCH" ]; then
  echo "refusing to run: current branch is '$BRANCH', this script is for '$REQUIRED_BRANCH' (git switch $REQUIRED_BRANCH)" >&2
  exit 1
fi
