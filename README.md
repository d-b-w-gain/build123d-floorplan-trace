# Build123D Floorplan Trace Example

This is a small Build123D tutorial example for turning a real-estate floorplan image into a simple 3D massing model. The model in `design.py` is intentionally data-driven: room plates, walls, doors, windows, fixtures, and the garage are declared as trace data, then generated into Build123D geometry.

The included `floorplan_trace_debug.svg` and `floorplan_trace_debug.png` are the important calibration aids. They overlay the generated trace on top of `floorplan.png`, making it much easier to correct wall runs, door openings, windows, and furniture placement before worrying about the 3D result.

## Files

- `design.py` - Build123D model and debug overlay generator.
- `floorplan.png` - source floorplan image used as the tracing reference.
- `floorplan_trace_debug.svg` - SVG overlay generated from the same model data.
- `floorplan_trace_debug.png` - rendered overlay image for quick review.

## Requirements

- Python 3.10+
- `build123d` for CAD generation

Install Build123D in your preferred environment:

```powershell
python -m pip install build123d
```

## Usage

Generate the CAD model by running or opening `design.py` in a Build123D-capable environment:

```powershell
python design.py
```

Regenerate the floorplan overlay:

```powershell
python design.py --svg floorplan_trace_debug.svg
```

The overlay works even when `build123d` is not installed, because it uses the same declarative trace data but writes SVG instead of CAD geometry.

## Debug Overlay Method

The workflow that made this example practical was:

1. Calibrate model coordinates to the source image in pixels.
2. Store walls, openings, windows, fixtures, and rooms as declarative trace records.
3. Generate both CAD geometry and an SVG overlay from those same records.
4. Draw the original floorplan under the trace, then inspect mismatches visually.
5. Adjust the trace records until the overlay matches the plan.

Useful prompt for future projects:

```text
Before building the CAD model, create a debug overlay from the same geometry data:
- use the floorplan image as the source of truth
- calibrate pixel coordinates to model units
- draw the original image underneath
- draw walls, doors, windows, rooms, and fixtures on top in distinct colors
- regenerate the overlay after each geometry change
- only trust the 3D model once the overlay matches the plan
```

This catches mistakes much earlier than looking at the 3D massing alone.
