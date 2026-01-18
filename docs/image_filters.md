# Artwork Image Filters

pixoo-spotify can process album artwork with a filter chain before rendering the GIF.
Use `--image-filters` with `|` to apply filters in order, for example:

```
--image-filters "blur:0.6|resize:32,box|posterize:4|quantize:32"
```

If you omit `--image-filters`, the default pipeline is used.
Use `--no-image-filters` to disable the chain and fall back to the legacy resize-only behavior.

## How the chain is applied

1. Artwork is converted to RGB.
2. Filters are applied in order.
3. The filtered artwork is scaled to the GIF canvas (nearest-neighbor) when the
   filtered size is smaller than the GIF size, which keeps the pixel-art look.
4. Unknown filter names raise an error.

## Filter classes and syntax

### ImageFilterChain
Applies a list of filters in order.

### Default pipeline (`default`)
Default pixel-art pipeline:

- `blur:0.6`
- `median:3`
- `posterize:4`
- `quantize:32,none`

You can also explicitly select it with:

```
default
```

### ImageFilterResize (`resize`)
Resize to a square size using a specific resampling filter.

Syntax:

```
resize:<size>[,<resample>]
```

- `<size>`: 16, 32, or 64
- `<resample>`: `nearest`, `box`, `bilinear`, `bicubic`, `lanczos` (default: `lanczos`)

### ImageFilterGaussianBlur (`blur`)
Light Gaussian blur to reduce moire and high-frequency noise.

Syntax:

```
blur[:<radius>]
```

- `<radius>`: float (default: 0.6)

### ImageFilterMedian (`median`)
Median filter for small noise suppression.

Syntax:

```
median[:<size>]
```

- `<size>`: odd integer >= 1 (default: 3)

### ImageFilterPosterize (`posterize`)
Reduce per-channel bit depth to emphasize blocky color steps.

Syntax:

```
posterize[:<bits>]
```

- `<bits>`: 1 to 8 (default: 4)

### ImageFilterQuantize (`quantize`)
Reduce palette size (no dither by default).

Syntax:

```
quantize[:<colors>[,<dither>]]
```

- `<colors>`: 2 to 256 (default: 32)
- `<dither>`: `none` or `floyd` (default: `none`)

### ImageFilterSharpen (`sharpen`)
Sharpen edges with a mild blend of PIL's SHARPEN filter.

Syntax:

```
sharpen[:<strength>]
```

- `<strength>`: 0.0 to 1.0 (default: 0.4)

## Examples

- Default pixel-art pass:

```
--image-filters "default"
```

- Disable image filters (legacy resize only):

```
--no-image-filters
```

- Manual chain tuned for softer moire suppression:

```
--image-filters "blur:0.8|resize:32,box|posterize:4|quantize:24"
```

- Keep sharp edges but reduce palette:

```
--image-filters "resize:32,box|quantize:32|sharpen:0.3"
```
