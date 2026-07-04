# Reference Images for Pill Detection

Place reference images here for Claude Vision training.

## Recommended Images

1. **pill_organizer_full.jpg** - Pills present in compartments
2. **pill_organizer_empty.jpg** - Empty compartments after pills taken
3. **pill_organizer_partial.jpg** - Some pills taken, some remaining

These help Claude Vision understand what to look for.

## Usage

The vision service (`backend/src/services/vision.ts`) analyzes uploaded images and compares against expected patterns.

For best results:
- Good lighting
- Clear view of compartments
- Consistent camera angle
