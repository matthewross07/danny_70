#!/usr/bin/env Rscript
# ==============================================================================
# scripts/render_sonicray_walk.R
# Alternative "Virgil / Dante Hazy Walk Through Memory Lane" prototype using
# Matthew Ross's `sonicray` Apple Silicon Metal hardware ray-tracing package.
#
# - Builds a continuous 74-km morphing 3D terrain corridor from 7 real DEM
#   landscapes (Amarillo plains -> Vallecito -> Pikes Peak foothills ->
#   Chalencon gorge -> Ouray San Juans -> Tenmile/Chamonix -> Mount Morrison).
# - Extrudes 540 real OpenStreetMap 3D building footprints (Tascosa High School,
#   Dick Bivins Stadium, Colorado Springs homes, Paris Notre-Dame, Rome Colosseum,
#   and Denver's Mile High Stadium) directly onto the terrain via sr_mesh_append()
#   so flat/urban realms cast real hardware ray-traced architectural shadows.
# - Walks a luminous dot (Danny: warm ivory core + International Klein Blue aura)
#   along a continuous meandering trail while clustered memory beacons bloom across
#   the surrounding slopes and buildings in approximate chronological order.
# ==============================================================================

suppressPackageStartupMessages({
  library(sonicray)
  library(jsonlite)
  library(png)
})

args <- commandArgs(trailingOnly = TRUE)
SHEET_ONLY    <- "--sheet-only" %in% args
HQ_MIN1       <- "--hq-min1" %in% args
METADATA_ONLY <- "--metadata-only" %in% args

DURATION_S    <- 300.0        # Full 5-minute chronological arc parameterizing Danny's walk
RENDER_DUR_S  <- if (HQ_MIN1) 60.0 else 300.0

if (HQ_MIN1) {
  # High-Quality 1080p First-Minute Review (Amarillo -> Palo Duro -> Tucumcari -> Vallecito)
  W         <- 1920L
  H_PX      <- 1080L
  PT_FPS    <- 3.0            # 181 native 1080p Metal path-traced keyframes across 60s
  OUT_FPS   <- 24L            # Silky 24 fps cinema playback
  SUBFRAMES <- as.integer(round(OUT_FPS / PT_FPS))
  AMB_SPP   <- 48L
  LIGHT_SPP <- 48L
  BOUNCES   <- 3L
  OUT_MP4   <- "media/sonicray_walk_hq_min1_base.mp4"
  OUT_JSON  <- "data/sonicray_walk_hq_min1.json"
  SHEET_PNG <- if (SHEET_ONLY) {
    "/Users/mrvr/.gemini/antigravity/brain/5e72ea41-a55f-4feb-80f8-d649f9941e22/scratch/walk_hq_min1_base_sheet.png"
  } else {
    "media/sonicray_walk_hq_min1_base_sheet.png"
  }
} else {
  # Draft / coarse 5-minute prototype parameters
  W         <- 768L
  H_PX      <- 432L
  PT_FPS    <- 2.5            # 751 hardware path-traced keyframes (every 0.40s)
  OUT_FPS   <- 20L            # 8x temporal blend -> smooth, dreamy 20 fps hazy walk
  SUBFRAMES <- as.integer(round(OUT_FPS / PT_FPS))
  AMB_SPP   <- 16L
  LIGHT_SPP <- 16L
  BOUNCES   <- 2L
  OUT_MP4   <- "media/sonicray_walk_draft_v2.mp4"
  OUT_JSON  <- "data/sonicray_walk.json"
  SHEET_PNG <- if (SHEET_ONLY) {
    "/Users/mrvr/.gemini/antigravity/brain/5e72ea41-a55f-4feb-80f8-d649f9941e22/scratch/walk_sheet.png"
  } else {
    "media/sonicray_walk_sheet.png"
  }
}
S_PX <- W / 768.0

cat("[walk] Checking sonicray Metal GPU...\n")
stopifnot(sr_metal_available())

# ------------------------------------------------------------------------------
# 1. Load Real DEM Landscapes & Real 3D OSM Building Footprints
# ------------------------------------------------------------------------------
dems_raw <- fromJSON("data/walk_dems.json", simplifyVector = FALSE)
bldg_raw <- fromJSON("data/walk_buildings.json", simplifyVector = FALSE)
mem_raw  <- fromJSON("data/memories.json", simplifyVector = FALSE)

# Corridor world bounds (km):
# In HQ_MIN1 (t = 0..60s, Danny walks z = 0 -> -13.1 km, camera sees ahead to -26 km),
# focus a dense ~25m x 28m terrain mesh over z in [-27.5, +3.5] for crisp ridges & streets!
XR <- c(-6.4, 6.4)
ZR <- if (HQ_MIN1) c(-27.5, 3.5) else c(-70.0, 4.0)
NR <- if (HQ_MIN1) 1220L else 888L
NC <- if (HQ_MIN1) 448L  else 160L
xs <- seq(XR[1], XR[2], length.out = NC)
zs <- seq(ZR[1], ZR[2], length.out = NR)

# Danny's continuous meandering footpath x(z): gentle valley bend + local trail sway
trail_x <- function(z) {
  1.35 * sin(-z * 0.085) + 0.52 * sin(-z * 0.27 + 0.4)
}

# 7 Chronological Realms ("Cantos") along z = 0 -> -65.5
cantos <- list(
  list(idx = 1L, id = "plains",    roman = "I",   era = "1956 – 1975", z_c = -3.6,  t0 =   0, t1 =  43,
       title = "Amarillo, Tascosa & Cousin Farms",   subtitle = "Texas Panhandle & Pennsylvania",
       relief_scale = 0.32, base_lift = 0.00,
       mems = c("m26", "m21", "m30", "m24", "m27", "m02")),
  list(idx = 2L, id = "mesas",     roman = "II",  era = "1976 – 1986", z_c = -13.0, t0 =  43, t1 =  85,
       title = "Asking Debbie, Tucumcari & Honeymoon Pines", subtitle = "Texas, New Mexico & Vallecito",
       relief_scale = 1.35, base_lift = 0.22,
       mems = c("m25", "m20", "m19", "m01")),
  list(idx = 3L, id = "foothills", roman = "III", era = "1988 – 2008", z_c = -23.0, t0 =  85, t1 = 128,
       title = "Foothills Home & Raising the Boys",  subtitle = "Colorado Springs, Monument & Adventures",
       relief_scale = 1.45, base_lift = 0.45,
       mems = c("m10", "m08", "m22", "m09", "m18", "m11", "m13", "m12")),
  list(idx = 4L, id = "france",    roman = "IV",  era = "2011 – 2018", z_c = -33.5, t0 = 128, t1 = 174,
       title = "Old-World Valleys, Cathedrals & Vineyards", subtitle = "France & Italy",
       relief_scale = 1.75, base_lift = 0.52,
       mems = c("m14", "extra_chalencon", "m15", "m05", "m16", "extra_msm",
                "extra_omaha", "extra_etretat", "extra_lecros", "extra_venice", "extra_florence", "extra_rome")),
  list(idx = 5L, id = "sanjuans",  roman = "V",   era = "2010 – 2021", z_c = -44.5, t0 = 174, t1 = 218,
       title = "Ouray Ridges & San Juan Elk Camps",  subtitle = "San Juan Wilderness, Colorado",
       relief_scale = 1.85, base_lift = 0.85,
       mems = c("m34", "m04", "m06", "extra_seanor", "extra_ryan", "m36", "m33", "m07", "m35")),
  list(idx = 6L, id = "summits",   roman = "VI",  era = "2018 – 2025", z_c = -54.5, t0 = 218, t1 = 260,
       title = "High Summits, Weddings & Sea Horizons", subtitle = "Breckenridge, Chamonix & Islands",
       relief_scale = 1.75, base_lift = 1.05,
       mems = c("m23", "m37", "m17", "m28", "extra_chamonix", "m29", "m31", "extra_stcyr")),
  list(idx = 7L, id = "morrison",  roman = "VII", era = "2026 · 70th", z_c = -64.0, t0 = 260, t1 = 300,
       title = "Red Rocks & Dawn on Mount Morrison", subtitle = "Seventy Years · Front Range",
       relief_scale = 2.05, base_lift = 1.18,
       mems = c("m32", "m03"))
)

# Helper to resample a 160x176 DEM list into NR x NC tiled/windowed along z
dem_mats <- lapply(seq_along(cantos), function(k) {
  raw_rows <- dems_raw$realms[[k]]$H
  nr0 <- length(raw_rows)
  nc0 <- length(raw_rows[[1]])
  M <- matrix(unlist(raw_rows), nrow = nr0, ncol = nc0, byrow = TRUE)
  # Normalize base to 22nd percentile (meters) so valleys meet cleanly
  base_m <- as.numeric(quantile(M, 0.22))
  (M - base_m) / 1000.0 * cantos[[k]]$relief_scale
})

# Stitch the 7 real DEMs smoothly along the 74-km z corridor (in scene km units, later *1000m for sr_mesh_from_heightfield)
H_km <- matrix(0.0, nrow = NR, ncol = NC)
realm_w_mat <- matrix(0.0, nrow = NR, ncol = length(cantos))

for (k in seq_along(cantos)) {
  zc <- cantos[[k]]$z_c
  # Smooth Gaussian support along z (sigma = 5.4 km gives seamless 4-km morph zones between realms)
  wk <- exp(-0.5 * ((zs - zc) / 5.4)^2)
  realm_w_mat[, k] <- wk
}
realm_w_mat <- sweep(realm_w_mat, 1, rowSums(realm_w_mat) + 1e-9, "/")

col_idx <- pmin(pmax(round(seq(1, ncol(dem_mats[[1]]), length.out = NC)), 1L), ncol(dem_mats[[1]]))

for (r in seq_len(NR)) {
  zr_val <- zs[r]
  row_acc <- numeric(NC)
  lift_acc <- 0.0
  for (k in seq_along(cantos)) {
    wk <- realm_w_mat[r, k]
    if (wk < 1e-4) next
    Dk <- dem_mats[[k]]
    nrk <- nrow(Dk)
    # Map local z around z_c (-8..+8 km) onto rows 1..nrk with mirror wrap
    u_row <- ((zr_val - (cantos[[k]]$z_c - 8.5)) / 17.0) * (nrk - 1) + 1
    u_mod <- ((u_row - 1) %% (2 * (nrk - 1)))
    if (u_mod > (nrk - 1)) u_mod <- 2 * (nrk - 1) - u_mod
    r0 <- max(1L, min(nrk - 1L, as.integer(floor(u_mod)) + 1L))
    fr <- u_mod - floor(u_mod)
    prof <- (1 - fr) * Dk[r0, col_idx] + fr * Dk[r0 + 1L, col_idx]
    row_acc <- row_acc + wk * prof
    lift_acc <- lift_acc + wk * cantos[[k]]$base_lift
  }
  # Gently grade a walkable valley floor along trail_x(zr_val) until Mount Morrison summit climb (z < -62.5)
  tx <- trail_x(zr_val)
  climb_summit <- max(0.0, min(1.0, (-62.2 - zr_val) / 3.2))
  valley_floor <- as.numeric(quantile(row_acc, 0.24))
  summit_ridge <- as.numeric(quantile(row_acc, 0.86)) + 0.32
  target_trail_h <- (1 - climb_summit) * valley_floor + climb_summit * summit_ridge
  corridor_mask <- exp(-((xs - tx) / 1.15)^2) * (1 - 0.55 * climb_summit)
  # Subtle tactile micro-relief: strata ledges on mesas/Red Rocks, canopy/talus texture in mountains, street grid in Amarillo
  amarillo_w <- realm_w_mat[r, 1]
  plain_mask <- exp(-((xs - tx) / 3.4)^2) * amarillo_w
  row_graded <- row_acc * (1 - 0.85 * plain_mask) + valley_floor * (0.85 * plain_mask)
  row_graded <- row_graded * (1 - 0.82 * corridor_mask) + target_trail_h * (0.82 * corridor_mask)
  # Geomorphic micro-detail (terraces & ridge ribs on high slopes only, keeping valley floors smooth & natural)
  valley_smooth <- exp(-((xs - tx) / 2.4)^2)
  rock_detail <- 0.015 * (1 - amarillo_w * 0.92) * (1 - corridor_mask) * (1 - 0.80 * valley_smooth) *
    (sin(xs * 7.3 + zr_val * 2.7) * cos(xs * 3.9 - zr_val * 5.1) + 0.40 * sin(xs * 17.0 - zr_val * 11.3))
  H_km[r, ] <- pmax(-0.15, row_graded + rock_detail) + lift_acc
}

# Helper to bilinearly sample H_km at arbitrary world (x, z)
sample_H_km <- function(x, z) {
  u <- pmin(pmax((x - XR[1]) / (XR[2] - XR[1]), 0), 1)
  v_row <- pmin(pmax((z - ZR[1]) / (ZR[2] - ZR[1]), 0), 1) # 0 at ZR[1] (row 1), 1 at ZR[2] (row NR)
  c_f <- u * (NC - 1) + 1
  r_f <- v_row * (NR - 1) + 1
  c0 <- pmin(pmax(as.integer(floor(c_f)), 1L), NC - 1L)
  r0 <- pmin(pmax(as.integer(floor(r_f)), 1L), NR - 1L)
  fc <- c_f - c0; fr <- r_f - r0
  (1 - fr) * ((1 - fc) * H_km[cbind(r0, c0)] + fc * H_km[cbind(r0, c0 + 1L)]) +
    fr * ((1 - fc) * H_km[cbind(r0 + 1L, c0)] + fc * H_km[cbind(r0 + 1L, c0 + 1L)])
}

# ------------------------------------------------------------------------------
# 2. Paint Linear Albedo Texture (Prairie Ochre -> Pine -> Old-World Slate -> Alpine -> Red Rocks)
#    with Subtle Klein Blue Twilight Undertones & Sunlit Footpath
# ------------------------------------------------------------------------------
TEX_H <- NR
TEX_W <- NC
albedo <- array(0.0, dim = c(TEX_H, TEX_W, 3L))

# Distinct linear RGB realm palettes so each era feels like a genuinely different world!
pal_low <- rbind(
  c(0.36, 0.23, 0.12), # I:   Amarillo warm panhandle ochre & golden grass
  c(0.30, 0.19, 0.12), # II:  New Mexico red-mesa desert & warm pine duff
  c(0.08, 0.19, 0.09), # III: Monument / Front Range deep ponderosa pine & golden aspen
  c(0.14, 0.19, 0.12), # IV:  Haute-Loire lush mossy gorge & vineyard terraces
  c(0.11, 0.17, 0.11), # V:   San Juan subalpine spruce & golden elk meadow
  c(0.10, 0.15, 0.22), # VI:  High alpine slate & coastal twilight
  c(0.38, 0.13, 0.07)  # VII: Red Rocks Fountain Formation rich crimson sandstone!
)
pal_high <- rbind(
  c(0.48, 0.33, 0.19), # I:   Palo Duro warm rimrock
  c(0.44, 0.31, 0.20), # II:  Sun-baked mesa sandstone
  c(0.34, 0.30, 0.24), # III: Pikes Peak warm pink-buff granite!
  c(0.38, 0.34, 0.27), # IV:  Warm French limestone cliffs & stone walls
  c(0.44, 0.43, 0.44), # V:   13,000-ft San Juan granite & snowfields
  c(0.52, 0.53, 0.58), # VI:  Glaciated Chamonix / Tenmile snow peaks
  c(0.52, 0.28, 0.16)  # VII: Mount Morrison sunlit warm gneiss & red hogback
)

for (r in seq_len(NR)) {
  zr_val <- zs[r]
  w_r <- realm_w_mat[r, ]
  c_lo <- as.numeric(w_r %*% pal_low)
  c_hi <- as.numeric(w_r %*% pal_high)
  h_row <- H_km[r, ]
  h_rel <- pmin(pmax((h_row - min(h_row)) / max(0.28, max(h_row) - min(h_row)), 0), 1)
  tx <- trail_x(zr_val)
  path_w <- exp(-((xs - tx) / 0.085)^2)
  # Subtle Amarillo street-grid lines in Canto I + golden aspen patches in Canto III/V
  grid_w <- realm_w_mat[r, 1] * exp(-((xs - tx) / 3.0)^2) *
    pmax(exp(-(sin(xs * 14.0)^2) / 0.012), exp(-(sin(zr_val * 14.0)^2) / 0.012)) * 0.35
  aspen_w <- (realm_w_mat[r, 3] + 0.8 * realm_w_mat[r, 5]) *
    pmax(0, sin(xs * 3.8 + zr_val * 1.9) * cos(xs * 2.3 - zr_val * 2.7)) * (1 - h_rel) * 0.55
  water_w <- (realm_w_mat[r, 4] + 0.7 * realm_w_mat[r, 6]) * exp(-((xs - (tx + 0.42)) / 0.18)^2)
  for (ch in 1:3) {
    col_line <- (1 - h_rel) * c_lo[ch] + h_rel * c_hi[ch]
    # Warm golden aspen groves on foothills & elk meadows
    aspen_col <- c(0.46, 0.31, 0.06)[ch]
    col_line <- (1 - aspen_w) * col_line + aspen_w * aspen_col
    # Amarillo dusty prairie avenues
    grid_col <- c(0.46, 0.38, 0.28)[ch]
    col_line <- (1 - grid_w) * col_line + grid_w * grid_col
    # River/sea Klein-tinted water
    riv_col <- c(0.02, 0.09, 0.38)[ch]
    col_line <- (1 - water_w) * col_line + water_w * riv_col
    # Warm sandstone footpath
    tr_col <- c(0.52, 0.46, 0.38)[ch]
    albedo[r, , ch] <- (1 - 0.65 * path_w) * col_line + (0.65 * path_w) * tr_col
  }
}

# Build base terrain mesh (H_km * 1000m with y0 = 0, vexag = 1 -> world y == H_km!)
terrain_mesh <- sr_mesh_from_heightfield(H_km * 1000.0, XR, ZR, y0 = 0.0, vexag = 1.0)

# ------------------------------------------------------------------------------
# 3. Extrude Real 3D OpenStreetMap Buildings onto Amarillo, Colorado Springs,
#    Paris (Notre-Dame), Rome (Colosseum), and Denver (Mile High) via sr_mesh_append!
# ------------------------------------------------------------------------------
extrude_footprint_prism <- function(pts_xy_km, y_base, height_km) {
  n <- nrow(pts_xy_km)
  if (n < 3 || height_km <= 0.002) return(NULL)
  # Ensure counter-clockwise 2D polygon orientation
  area2 <- sum(pts_xy_km[, 1] * pts_xy_km[c(2:n, 1), 2] - pts_xy_km[c(2:n, 1), 1] * pts_xy_km[, 2])
  if (area2 < 0) pts_xy_km <- pts_xy_km[n:1, , drop = FALSE]

  y_top <- y_base + height_km
  # Wall quads (4 vertices per edge for crisp flat-shaded architectural facets!)
  v_list <- list()
  n_list <- list()
  t_list <- list()
  v_count <- 0L

  for (i in seq_len(n)) {
    j <- if (i == n) 1L else i + 1L
    x0 <- pts_xy_km[i, 1]; z0 <- pts_xy_km[i, 2]
    x1 <- pts_xy_km[j, 1]; z1 <- pts_xy_km[j, 2]
    dx <- x1 - x0; dz <- z1 - z0
    len <- sqrt(dx * dx + dz * dz)
    if (len < 1e-5) next
    nx <- dz / len; nz <- -dx / len
    wv <- rbind(
      c(x0, y_base - 0.015, z0),
      c(x1, y_base - 0.015, z1),
      c(x1, y_top,          z1),
      c(x0, y_top,          z0)
    )
    wn <- matrix(c(nx, 0, nz), nrow = 4, ncol = 3, byrow = TRUE)
    wt <- rbind(c(0L, 1L, 2L), c(0L, 2L, 3L)) + v_count
    v_list[[length(v_list) + 1L]] <- wv
    n_list[[length(n_list) + 1L]] <- wn
    t_list[[length(t_list) + 1L]] <- wt
    v_count <- v_count + 4L
  }

  # Roof fan around centroid (accurate for convex & star-shaped OSM footprints + stadiums)
  cx <- mean(pts_xy_km[, 1]); cz <- mean(pts_xy_km[, 2])
  rv <- rbind(c(cx, y_top, cz), cbind(pts_xy_km[, 1], rep(y_top, n), pts_xy_km[, 2]))
  rn <- matrix(c(0, 1, 0), nrow = n + 1L, ncol = 3, byrow = TRUE)
  rt <- cbind(rep(0L, n), seq_len(n), c(2:n, 1L)) + v_count
  v_list[[length(v_list) + 1L]] <- rv
  n_list[[length(n_list) + 1L]] <- rn
  t_list[[length(t_list) + 1L]] <- rt

  verts <- do.call(rbind, v_list)
  norms <- do.call(rbind, n_list)
  tris  <- do.call(rbind, t_list)
  storage.mode(tris) <- "integer"

  # Assign world-consistent (u, v) so distance haze works identically on buildings & terrain!
  u <- pmin(pmax((verts[, 1] - XR[1]) / (XR[2] - XR[1]), 0.001), 0.999)
  v <- pmin(pmax(1.0 - (verts[, 3] - ZR[1]) / (ZR[2] - ZR[1]), 0.001), 0.999)
  list(vertices = verts, normals = norms, uvs = cbind(u, v), indices = tris, mesh_dims = c(0L, 0L))
}

# Placement anchors along Danny's corridor:
# Broad xy_scale + deterministic outskirts thinning dissolves any circular patch edge
# so Amarillo reads as a continuous horizon-wide Panhandle city tapering naturally into ranchland!
cluster_placements <- list(
  amarillo_home    = list(src = "amarillo_bivins",  z_center = -0.5, side =  1.0, offset_x = 0.25, xy_scale = 2.05, h_exag = 2.9, max_r = 1150, rot = pi * 0.5, col = c(0.57, 0.45, 0.34)),
  amarillo_tascosa = list(src = "amarillo_tascosa", z_center = -2.6, side = -1.0, offset_x = 0.28, xy_scale = 2.05, h_exag = 3.1, max_r = 1250, rot = 0.0,      col = c(0.58, 0.45, 0.33)),
  amarillo_bivins  = list(src = "amarillo_bivins",  z_center = -5.1, side =  1.0, offset_x = 0.30, xy_scale = 2.05, h_exag = 3.3, max_r = 1150, rot = 0.0,      col = c(0.60, 0.50, 0.39)),
  tucumcari_rt66   = list(src = "tucumcari_rt66",   z_center = -12.9, side = 1.0, offset_x = 0.22, xy_scale = 1.85, h_exag = 3.1, max_r = 950,  rot = 0.0,      col = c(0.56, 0.42, 0.31)),
  monument_homes   = list(src = "monument_homes",   z_center = -23.2, side = -1.0, offset_x = 0.35, xy_scale = 1.75, h_exag = 3.2, max_r = 1100, rot = 0.0,      col = c(0.52, 0.42, 0.32)),
  paris_notredame  = list(src = "paris_notredame",  z_center = -32.2, side = -1.0, offset_x = 0.50, xy_scale = 1.75, h_exag = 3.0, max_r = 720,  rot = 0.0,      col = c(0.58, 0.52, 0.43)),
  rome_colosseum   = list(src = "rome_colosseum",   z_center = -35.6, side =  1.0, offset_x = 0.50, xy_scale = 1.80, h_exag = 3.5, max_r = 720,  rot = 0.0,      col = c(0.62, 0.47, 0.34)),
  denver_milehigh  = list(src = "denver_milehigh",  z_center = -61.4, side =  1.0, offset_x = 0.60, xy_scale = 1.80, h_exag = 3.7, max_r = 850,  rot = 0.0,      col = c(0.50, 0.53, 0.62))
)

bldg_by_id <- setNames(bldg_raw$clusters, vapply(bldg_raw$clusters, `[[`, "", "id"))
bldg_meshes <- list()
for (placement_name in names(cluster_placements)) {
  cfg <- cluster_placements[[placement_name]]
  cl <- bldg_by_id[[cfg$src]]
  if (is.null(cl)) next
  if (cfg$z_center < ZR[1] + 1.5 || cfg$z_center > ZR[2] - 0.2) next
  tx0 <- trail_x(cfg$z_center)
  anchor_x <- tx0 + cfg$side * cfg$offset_x
  anchor_z <- cfg$z_center
  ca <- cos(cfg$rot); sa <- sin(cfg$rot)

  for (fp in cl$footprints) {
    pts_raw <- do.call(rbind, lapply(fp$pts_m, as.numeric))
    pts_m <- cbind(pts_raw[, 1] * ca - pts_raw[, 2] * sa, pts_raw[, 1] * sa + pts_raw[, 2] * ca)
    pts_km <- cbind(
      anchor_x + (pts_m[, 1] / 1000.0) * cfg$xy_scale,
      anchor_z - (pts_m[, 2] / 1000.0) * cfg$xy_scale
    )
    cx <- mean(pts_km[, 1]); cz <- mean(pts_km[, 2])
    if (cz < ZR[1] + 0.3 || cz > ZR[2] - 0.3) next
    # Keep Danny's central tree-lined walking avenue (|x - trail_x(z)| < 0.17 km) clear!
    if (abs(cx - trail_x(cz)) < 0.17 || abs(cx) > 5.8) next

    dist_ratio <- min(1.0, (if (!is.null(fp$dist_m)) as.numeric(fp$dist_m) else 300.0) / cfg$max_r)
    # Organic suburban outskirts feathering: dissolve circular boundary into scattered farmsteads!
    if (dist_ratio > 0.52) {
      keep_prob <- max(0.04, (1.0 - (dist_ratio - 0.52) / 0.48)^1.65)
      h_det <- ((abs(round(cx * 997 + cz * 1999)) %% 1000L) / 1000.0)
      if (h_det > keep_prob && as.numeric(fp$span_m) < 42.0) next
    }

    yb <- sample_H_km(cx, cz)
    edge_taper <- 1.0 - 0.42 * (dist_ratio^2)
    hk <- (as.numeric(fp$h_m) / 1000.0) * cfg$h_exag * edge_taper
    prism <- extrude_footprint_prism(pts_km, yb, hk)
    if (!is.null(prism)) {
      bldg_meshes[[length(bldg_meshes) + 1L]] <- prism
      shade_var <- 0.84 + ((abs(round(cx * 37 + cz * 53)) %% 33) / 100.0)
      u_c <- (cx - XR[1]) / (XR[2] - XR[1])
      v_c <- 1.0 - (cz - ZR[1]) / (ZR[2] - ZR[1])
      albedo <- sr_paint_albedo(albedo, c(u_c, v_c), pmin(0.85, cfg$col * shade_var), half_px = 1L)
    }
  }
}

# Add 4 stadium floodlight stanchions around Dick Bivins Stadium in Amarillo (realistic stadium height)
biv_cfg <- cluster_placements$amarillo_bivins
biv_x <- trail_x(biv_cfg$z_center) + biv_cfg$side * biv_cfg$offset_x
biv_z <- biv_cfg$z_center
for ( sx in c(-0.18, 0.18) ) {
  for ( sz in c(-0.20, 0.20) ) {
    px <- biv_x + sx; pz <- biv_z + sz
    yb <- sample_H_km(px, pz)
    tower <- cbind(px + c(-0.012, 0.012, 0.012, -0.012), pz + c(-0.012, -0.012, 0.012, 0.012))
    bldg_meshes[[length(bldg_meshes) + 1L]] <- extrude_footprint_prism(tower, yb, 0.088)
  }
}

if (!METADATA_ONLY) {
  cat(sprintf("[walk] Appending %d real 3D architectural prisms to 74-km terrain corridor...\n", length(bldg_meshes)))
  if (length(bldg_meshes) > 0) {
    # Batch merge all building vertices/normals/uvs/indices in one fast O(N) step
    v_all <- lapply(bldg_meshes, `[[`, "vertices")
    n_all <- lapply(bldg_meshes, `[[`, "normals")
    u_all <- lapply(bldg_meshes, `[[`, "uvs")
    nv_each <- vapply(v_all, nrow, 0L)
    offsets <- c(0L, cumsum(nv_each)[-length(nv_each)])
    i_all <- Map(function(m, off) m$indices + off, bldg_meshes, offsets)
    combined_bldgs <- list(
      vertices  = do.call(rbind, v_all),
      normals   = do.call(rbind, n_all),
      uvs       = do.call(rbind, u_all),
      indices   = do.call(rbind, i_all),
      mesh_dims = c(0L, 0L)
    )
    full_mesh <- sr_mesh_append(terrain_mesh, combined_bldgs)
  } else {
    full_mesh <- terrain_mesh
  }

  cat(sprintf("[walk] Uploading unified mesh (%d vertices, %d triangles) to Apple Metal BVH...\n",
              nrow(full_mesh$vertices), nrow(full_mesh$indices)))
  gpu_scene <- sr_upload_mesh(full_mesh, albedo, water = NULL)
}

# ------------------------------------------------------------------------------
# 4. Place All 49 Memories in Clustered 3D Coordinates Across the 7 Cantos
# ------------------------------------------------------------------------------
mem_by_id <- setNames(mem_raw$memories, vapply(mem_raw$memories, `[[`, "", "id"))
placed_memories <- list()

for (k in seq_along(cantos)) {
  canto <- cantos[[k]]
  mids <- canto$mems
  nm <- length(mids)
  # Spread clustered memories across a ~6.2 km stretch centered on canto$z_c
  z_span <- min(6.6, max(3.6, nm * 0.58))
  z_slots <- seq(canto$z_c + z_span * 0.48, canto$z_c - z_span * 0.48, length.out = nm)

  for (j in seq_len(nm)) {
    mid <- mids[j]
    m <- mem_by_id[[mid]]
    if (is.null(m)) next
    mz <- z_slots[j]
    # Alternate left & right hillsides/buildings in natural staggered clusters
    side <- if (j %% 2L == 1L) -1.0 else 1.0
    dist_off <- 0.55 + ((j * 37L) %% 5L) * 0.34 # 0.55 .. 1.91 km off the trail
    if (k == 7L && mid == "m03") {
      # Final stop (#49 Mount Morrison) right near the summit crest ahead of Danny!
      dist_off <- 0.22; side <- 1.0; mz <- -65.2
    }
    mx <- trail_x(mz) + side * dist_off
    my <- sample_H_km(mx, mz) + 0.14

    # Palette accent: alternate warm golden memory glow & International Klein Blue (#002FA7)
    pal_type <- if (j %% 3L == 0L) "klein" else if (j %% 3L == 1L) "gold" else "ivory"
    glow_rgb <- switch(pal_type,
      klein = c(0.06, 0.28, 1.35),
      gold  = c(1.25, 0.68, 0.22),
      ivory = c(1.05, 0.88, 0.68)
    )

    placed_memories[[length(placed_memories) + 1L]] <- list(
      uid      = sprintf("pm_%02d", length(placed_memories) + 1L),
      id       = m$id,
      canto    = k,
      roman    = canto$roman,
      era      = canto$era,
      title    = m$title,
      place    = m$place,
      coords   = if (!is.null(m$coords)) as.numeric(m$coords) else c(-101.83, 35.20),
      author   = if (is.null(m$author)) "" else m$author,
      text     = if (is.null(m$text)) "" else m$text,
      media    = m$media,
      x        = round(mx, 4),
      y        = round(my, 4),
      z        = round(mz, 4),
      pal_type = pal_type,
      glow_rgb = glow_rgb
    )
  }
}
cat(sprintf("[walk] Positioned %d clustered memories across 7 chronological landscapes.\n", length(placed_memories)))

# Physical 3D Landscape Waypoints anchored directly onto the DEM & OSM town districts
landscape_waypoints <- list(
  list(id = "wp_tascosa",   z = -2.7,  dx = -0.78, dy = 0.12, label = "Tascosa High School & Neighborhoods", sub = "Amarillo, Texas · 3,655 ft",       lon = -101.8825, lat = 35.2038),
  list(id = "wp_bivins",    z = -5.2,  dx =  0.80, dy = 0.14, label = "Dick Bivins Stadium & East Blocks",   sub = "Amarillo, Texas · 3,645 ft",       lon = -101.7907, lat = 35.1955),
  list(id = "wp_caprock",   z = -8.6,  dx = -0.95, dy = 0.10, label = "Palo Duro & Caprock Escarpment",      sub = "Leaving the Panhandle Plains",     lon = -101.6800, lat = 34.9800),
  list(id = "wp_tucumcari", z = -12.8, dx =  0.76, dy = 0.13, label = "Historic Route 66 Boulevard",          sub = "Tucumcari, New Mexico · 4,090 ft", lon = -103.7250, lat = 35.1717),
  list(id = "wp_vallecito", z = -16.8, dx = -0.90, dy = 0.16, label = "Vallecito Creek & Pine Foothills",     sub = "San Juan Range, Colorado · 7,890 ft", lon = -107.5700, lat = 37.3800),
  list(id = "wp_monument",  z = -23.0, dx = -0.82, dy = 0.14, label = "Pikes Peak Foothills & Pine Vista",    sub = "Monument & Colorado Springs, CO",  lon = -104.8600, lat = 39.0900),
  list(id = "wp_paris",     z = -32.0, dx = -0.85, dy = 0.15, label = "Île de la Cité & Notre-Dame",          sub = "Paris, France",                    lon = 2.3499,    lat = 48.8530),
  list(id = "wp_loire",     z = -33.8, dx =  0.65, dy = 0.08, label = "Gorges de la Loire · Chalencon",       sub = "Haute-Loire, France",              lon = 3.9860,    lat = 45.2890),
  list(id = "wp_rome",      z = -35.6, dx =  0.85, dy = 0.15, label = "Colosseum & Historic Center",          sub = "Rome, Italy",                      lon = 12.4922,   lat = 41.8902),
  list(id = "wp_ouray",     z = -44.5, dx = -0.95, dy = 0.18, label = "Ouray Ridges & San Juan Elk Cirques",  sub = "Colorado Wilderness · 11,400 ft",  lon = -107.6700, lat = 38.0200),
  list(id = "wp_tenmile",   z = -54.5, dx = -0.90, dy = 0.18, label = "Tenmile Range & Alpine Summits",       sub = "Breckenridge, CO · 11,800 ft",     lon = -106.0500, lat = 39.4800),
  list(id = "wp_morrison",  z = -64.8, dx =  0.45, dy = 0.18, label = "Red Rocks & Mount Morrison Crest",     sub = "Morrison, Colorado · 7,881 ft",    lon = -105.2200, lat = 39.6690)
)
for (idx_w in seq_along(landscape_waypoints)) {
  wp <- landscape_waypoints[[idx_w]]
  wx <- trail_x(wp$z) + wp$dx
  wy <- if (wp$z >= ZR[1] && wp$z <= ZR[2]) sample_H_km(wx, wp$z) + wp$dy else 0.5
  landscape_waypoints[[idx_w]]$x <- round(wx, 4)
  landscape_waypoints[[idx_w]]$y <- round(wy, 4)
}

# Continuous ground-truth terrain reference along z for the live Terrain Underfoot HUD & Dual-Pin Map
terrain_nodes <- data.frame(
  z       = c(  0.0,  -6.2,  -9.5, -13.2, -17.5, -24.0, -33.5, -44.5, -54.5, -65.3),
  lon     = c(-101.86, -101.79, -102.40, -103.73, -107.57, -104.85,  3.98, -107.67, -106.05, -105.22),
  lat     = c( 35.20,   35.19,   35.05,   35.17,   37.38,   39.02,  45.29,  38.02,   39.48,   39.67),
  elev_ft = c(  3655,    3645,    3820,    4090,    7890,    6950,   1850,  11200,   11600,    7881),
  region  = c("Amarillo Plains, Texas", "Amarillo & Palo Duro Rim, TX", "Caprock Escarpment, TX/NM",
              "Route 66 · Tucumcari, New Mexico", "Vallecito Pines · San Juan Range, CO",
              "Front Range Foothills, Colorado", "Haute-Loire Gorge, France",
              "San Juan Elk Country, Colorado", "Tenmile Alpine Ridge, Colorado",
              "Red Rocks & Mount Morrison, CO"),
  stringsAsFactors = FALSE
)

terrain_at_z <- function(z_val) {
  # Interpolate lon, lat, elev_ft and pick nearest region label
  ord <- order(terrain_nodes$z)
  zn <- terrain_nodes$z[ord]
  lon_i <- approx(zn, terrain_nodes$lon[ord], xout = z_val, rule = 2)$y
  lat_i <- approx(zn, terrain_nodes$lat[ord], xout = z_val, rule = 2)$y
  el_i  <- round(approx(zn, terrain_nodes$elev_ft[ord], xout = z_val, rule = 2)$y / 10) * 10
  k_near <- which.min(abs(terrain_nodes$z - z_val))
  list(lon = round(lon_i, 3), lat = round(lat_i, 3), elev_ft = as.integer(el_i), label = terrain_nodes$region[k_near])
}

# ------------------------------------------------------------------------------
# 5. Camera, Walker Path & Virgil/Dante Hazy Linear-Light Compositor
# ------------------------------------------------------------------------------
# Danny walks smoothly from z = 0.0 (t = 0s) to z = -65.3 (t = 300s)
danny_state <- function(t) {
  u <- min(max(t / DURATION_S, 0.0), 1.0)
  # Gentle ease at very start and summit arrival
  u_smooth <- 0.04 * (u * u * (3 - 2 * u)) + 0.96 * u
  z_d <- 0.0 - 65.3 * u_smooth
  x_d <- trail_x(z_d)
  y_d <- sample_H_km(x_d, z_d)

  # Camera glides 3.45 km behind and ~1.12 km above Danny, gently swaying like a walking companion (Virgil)
  z_cam <- z_d + 3.45
  x_cam <- trail_x(z_d + 2.6) * 0.82 + 0.16 * sin(t * 0.07)
  y_ground_cam <- sample_H_km(x_cam, z_cam)
  y_cam <- max(y_d + 1.10, y_ground_cam + 0.88) + 0.04 * sin(t * 0.11)

  # Keep Danny consistently framed in the lower-middle third while looking down the morphing valley
  z_look <- z_d - 3.6
  x_look <- trail_x(z_d - 2.4) * 0.88
  y_ahead <- sample_H_km(x_look, z_look)
  y_look <- 0.68 * (y_d + 0.22) + 0.32 * (y_ahead + 0.18)

  list(
    danny    = c(x_d, y_d, z_d),
    lookfrom = c(x_cam, y_cam, z_cam),
    lookat   = c(x_look, y_look, z_look),
    fov      = 31.0,
    u        = u
  )
}

# Precompute pixel grids (row-major length W * H_PX) for sky, stars & sprites
npix <- W * H_PX
px_x <- rep(seq_len(W) - 0.5, times = H_PX)
px_y <- rep(seq_len(H_PX) - 0.5, each = W)
yn_vec <- px_y / (H_PX - 1.0) # 0 at top, 1 at bottom

# Deterministic starfield in upper sky (scaled cleanly to resolution)
set.seed(1956L)
star_r <- numeric(npix); star_g <- numeric(npix); star_b <- numeric(npix)
n_stars <- as.integer(round(260L * S_PX))
sx_i <- sample.int(W, n_stars, replace = TRUE)
sy_i <- sample.int(as.integer(H_PX * 0.68), n_stars, replace = TRUE)
s_br <- runif(n_stars, 0.25, 0.98)^2
star_rad <- if (S_PX >= 2.0) 1L else 0L
for (i in seq_len(n_stars)) {
  is_blue <- (i %% 4L == 0L)
  for (dy_s in (-star_rad):star_rad) {
    for (dx_s in (-star_rad):star_rad) {
      xx <- sx_i[i] + dx_s; yy <- sy_i[i] + dy_s
      if (xx >= 1L && xx <= W && yy >= 1L && yy <= H_PX) {
        fall <- if (dx_s == 0L && dy_s == 0L) 1.0 else 0.38
        idx <- (yy - 1L) * W + xx
        star_r[idx] <- pmax(star_r[idx], s_br[i] * fall * (if (is_blue) 0.55 else 1.0))
        star_g[idx] <- pmax(star_g[idx], s_br[i] * fall * (if (is_blue) 0.75 else 0.96))
        star_b[idx] <- pmax(star_b[idx], s_br[i] * fall * 1.0)
      }
    }
  }
}

# Render & composite a single timestamp `t` -> returns list(rgb_lin = matrix(3, npix), proj = ...)
render_walk_keyframe <- function(t) {
  st <- danny_state(t)
  d_pos <- st$danny

  # Build dynamic multi-light batch:
  #  1) danny_core  : intense tight warm sphere casting crisp architectural & boulder shadows
  #  2) danny_klein : elevated Klein Blue (#002FA7) aura sphere bathing nearby ground & facades
  #  3) moon_dawn   : high distant directional-like fill sphere for soft rim relief on mountains
  #  4..K) active clustered memory beacons within [-11.5 km ahead .. +2.5 km behind] of Danny
  lt_rows <- list(
    data.frame(name = "danny_core",  x = d_pos[1], y = d_pos[2] + 0.12, z = d_pos[3], r = 0.07, intensity = 26.0, stringsAsFactors = FALSE),
    data.frame(name = "danny_klein", x = d_pos[1], y = d_pos[2] + 0.32, z = d_pos[3] + 0.06, r = 0.26, intensity = 34.0, stringsAsFactors = FALSE),
    data.frame(name = "rim_light",   x = d_pos[1] - 7.5, y = d_pos[2] + 6.8, z = d_pos[3] - 11.0, r = 2.0, intensity = 340.0, stringsAsFactors = FALSE)
  )

  active_mems <- list()
  for (pm in placed_memories) {
    dz <- pm$z - d_pos[3] # negative = ahead of Danny
    if (dz <= 1.8 && dz >= -10.5) {
      # Smooth bell activation as Danny approaches and walks through the memory cluster
      w_mem <- exp(-0.5 * ((dz + 3.0) / 3.1)^2)
      if (w_mem > 0.05) {
        lt_rows[[length(lt_rows) + 1L]] <- data.frame(
          name = pm$uid, x = pm$x, y = pm$y + 0.15, z = pm$z,
          r = 0.15, intensity = 46.0 * w_mem, stringsAsFactors = FALSE
        )
        active_mems[[length(active_mems) + 1L]] <- list(pm = pm, w = w_mem)
      }
    }
  }
  # Cap at 16 lights so sonicray always executes in a SINGLE GPU BVH batch!
  if (length(lt_rows) > 16L) lt_rows <- lt_rows[1:16]
  lt <- do.call(rbind, lt_rows)

  res <- suppressMessages(sr_render_light_layers(
    gpu_scene   = gpu_scene,
    light_table = lt,
    lookfrom    = st$lookfrom,
    lookat      = st$lookat,
    fov         = st$fov,
    width       = W,
    height      = H_PX,
    amb_spp     = AMB_SPP,
    light_spp   = LIGHT_SPP,
    max_bounces = BOUNCES,
    clamp       = 28.0,
    batch_size  = 16L
  ))

  # Extract interleaved linear AOVs: [3, npix]
  amb  <- matrix(res$aovs$amb, nrow = 3L, ncol = npix)
  mask <- pmin(pmax(res$aovs$mask, 0.0), 1.0)
  uv_m <- matrix(res$aovs$uv, nrow = 2L, ncol = npix)

  # Subtle seasonal/time-of-night progression across the 70-year walk, culminating in Mount Morrison dawn!
  dawn <- max(0.0, min(1.0, (st$u - 0.76) / 0.22))
  dawn <- dawn * dawn * (3.0 - 2.0 * dawn)
  warm_era <- exp(-((st$u - 0.12) / 0.16)^2) * 0.35 # Subtle warm Texas golden-dusk memory glow in Canto I-II

  # Balanced silvery-twilight ambient fill so true earth/pine/limestone/Red-Rocks colors shine through!
  amb_tint <- c(
    0.18 * (1 - dawn) + 0.48 * dawn + 0.08 * warm_era,
    0.19 * (1 - dawn) + 0.38 * dawn + 0.04 * warm_era,
    0.29 * (1 - dawn) + 0.42 * dawn
  )
  lin <- amb * amb_tint

  # Danny's warm core lantern + localized International Klein Blue (#002FA7) aura right around him!
  l_core  <- matrix(res$layers[["danny_core"]],  nrow = 3L, ncol = npix)
  l_klein <- matrix(res$layers[["danny_klein"]], nrow = 3L, ncol = npix)
  l_rim   <- matrix(res$layers[["rim_light"]],   nrow = 3L, ncol = npix)

  lin <- lin + l_core  * c(1.95, 1.38, 0.82)
  lin <- lin + l_klein * c(0.02, 0.19, 1.85) # Focused International Klein Blue accent around Danny!
  # Grazing directional twilight/moonlight -> dawn sun rim sculpting every ridge & building wall!
  rim_tint <- c(
    0.58 * (1 - dawn) + 1.45 * dawn + 0.25 * warm_era,
    0.56 * (1 - dawn) + 0.82 * dawn + 0.12 * warm_era,
    0.76 * (1 - dawn) + 0.50 * dawn
  )
  lin <- lin + l_rim * rim_tint * 0.44

  # Add clustered memory lights on surrounding buildings, ledges & cirques
  for (am in active_mems) {
    uid <- am$pm$uid
    if (!is.null(res$layers[[uid]])) {
      lm <- matrix(res$layers[[uid]], nrow = 3L, ncol = npix)
      lin <- lin + lm * (am$pm$glow_rgb * 1.30)
    }
  }

  # ACES filmic tone mapping on terrain
  mx <- pmax(lin[1L, ], lin[2L, ], lin[3L, ])
  mc <- ifelse(mx > 0.55, 0.55 + (mx - 0.55) / (1.0 + 1.6 * (mx - 0.55)), mx)
  scale_k <- mc / pmax(mx, 1e-6)
  for (ch in 1:3) lin[ch, ] <- pmax(lin[ch, ] * scale_k, 0.0)
  mapped <- (lin * (2.51 * lin + 0.03)) / (lin * (2.43 * lin + 0.59) + 0.14)
  terr_srgb <- pmin(pmax(mapped, 0.0), 1.0)^(1.0 / 2.2)

  # Virgil/Dante Sky Gradient: deep indigo-Klein zenith -> dusky violet-amber / dawn horizon mist
  zen_col <- c(0.014 * (1 - dawn) + 0.04 * dawn,
               0.028 * (1 - dawn) + 0.13 * dawn,
               0.135 * (1 - dawn) + 0.44 * dawn)
  hor_col <- c(0.135 * (1 - dawn) + 0.86 * dawn + 0.08 * warm_era,
               0.165 * (1 - dawn) + 0.52 * dawn + 0.04 * warm_era,
               0.390 * (1 - dawn) + 0.44 * dawn)
  mist_band <- exp(-((yn_vec - 0.45) / 0.20)^2)
  yn_curve <- pmin(1.0, yn_vec^1.2)
  twinkle <- (0.82 + 0.18 * sin(t * 1.8 + px_x * 0.13)) * (1.0 - 0.85 * dawn) * pmax(0.0, 1.0 - yn_vec * 2.1)
  sky_srgb <- rbind(
    pmin(1.0, (1 - yn_curve) * zen_col[1] + yn_curve * hor_col[1] + 0.08 * mist_band * (1 + 2.0 * dawn) + star_r * twinkle),
    pmin(1.0, (1 - yn_curve) * zen_col[2] + yn_curve * hor_col[2] + 0.08 * mist_band * (1 + 0.8 * dawn) + star_g * twinkle),
    pmin(1.0, (1 - yn_curve) * zen_col[3] + yn_curve * hor_col[3] + 0.14 * mist_band * (1 - 0.2 * dawn) + star_b * twinkle)
  )

  # Exact 3D pixel world coordinates from first-hit UV:
  # 1) Distance fog (> 13 km melts seamlessly into horizon sky)
  # 2) Low-lying Virgil/Dante valley mist pooling in river gorges & hollows while peaks rise above!
  u_hit <- uv_m[1L, ]
  v_hit <- uv_m[2L, ]
  x_hit <- XR[1] + u_hit * (XR[2] - XR[1])
  z_hit <- ZR[1] + (1.0 - v_hit) * (ZR[2] - ZR[1])
  dist_km <- pmax(0.0, st$lookfrom[3] - z_hit)
  fog_w <- pmin(1.0, (1.0 - exp(-((pmax(dist_km - 1.8, 0.0)) / 6.5)^1.6)))
  eff_mask <- mask * (1.0 - fog_w)

  y_hit <- sample_H_km(x_hit, z_hit)
  valley_ref <- sample_H_km(trail_x(z_hit), z_hit)
  elev_above_valley <- pmax(0.0, y_hit - valley_ref)
  # Dreamy ground mist pooled in low valleys (strongest 2.5..10 km ahead, clearing right around Danny)
  valley_mist <- mask * (1.0 - fog_w) * exp(-elev_above_valley / 0.24) *
    (1.0 - exp(-0.28 * pmax(dist_km - 1.2, 0.0))) * 0.56
  mist_rgb <- c(
    0.16 * (1 - dawn) + 0.78 * dawn,
    0.22 * (1 - dawn) + 0.54 * dawn,
    0.52 * (1 - dawn) + 0.56 * dawn
  )
  for (ch in 1:3) {
    terr_srgb[ch, ] <- terr_srgb[ch, ] * (1.0 - valley_mist) + mist_rgb[ch] * valley_mist
  }

  img <- sweep(sky_srgb, 2L, 1.0 - eff_mask, "*") + sweep(terr_srgb, 2L, eff_mask, "*")

  # Project Luminous Danny & Clustered Memory Lanterns via sonicray::sr_project()
  d_scr <- sr_project(matrix(c(d_pos[1], d_pos[2] + 0.11, d_pos[3]), nrow = 1),
                      st$lookfrom, st$lookat, st$fov, W, H_PX)
  dx_d <- px_x - d_scr[1, 1]
  dy_d <- px_y - d_scr[1, 2]
  r2_d <- dx_d * dx_d + dy_d * dy_d

  # Danny's iconic International Klein Blue (#002FA7) corona + warm incandescent pearl core (scaled by S_PX)!
  aura_klein <- exp(-0.5 * r2_d / ((24.0 * S_PX)^2)) * 0.52 + exp(-0.5 * r2_d / ((10.0 * S_PX)^2)) * 0.68
  core_warm  <- exp(-0.5 * r2_d / ((3.2 * S_PX)^2)) * 1.20
  img[1L, ] <- img[1L, ] + aura_klein * 0.02 + core_warm * 1.00
  img[2L, ] <- img[2L, ] + aura_klein * 0.22 + core_warm * 0.95
  img[3L, ] <- img[3L, ] + aura_klein * 1.05 + core_warm * 0.88

  # Soft, organic hazy lantern halos on clustered hillside memories (scaled by S_PX!)
  win_px <- ceiling(44.0 * S_PX)
  tap_px <- 42.0 * S_PX
  proj_mems <- list()
  for (am in active_mems) {
    pm <- am$pm
    m_scr <- sr_project(matrix(c(pm$x, pm$y + 0.08, pm$z), nrow = 1),
                        st$lookfrom, st$lookat, st$fov, W, H_PX)
    mpx <- m_scr[1, 1]; mpy <- m_scr[1, 2]
    if (mpx >= -win_px && mpx <= W + win_px && mpy >= -win_px && mpy <= H_PX + win_px) {
      dxm <- px_x - mpx
      dym <- mpy - px_y
      near <- which(abs(dxm) <= win_px & abs(dym) <= win_px)
      if (length(near) > 0) {
        r2m <- dxm[near]^2 + dym[near]^2
        taper <- pmax(0.0, 1.0 - r2m / (tap_px^2))^2
        halo <- exp(-0.5 * r2m / ((11.5 * S_PX)^2)) * taper * am$w * 0.42
        orb  <- exp(-0.5 * r2m / ((2.6 * S_PX)^2))  * taper * am$w * 0.95
        wisp <- ifelse(dym[near] > 0, exp(-0.5 * (dxm[near] / (3.2 * S_PX))^2) * exp(-dym[near] / (9.5 * S_PX)) * taper * am$w * 0.26, 0.0)
        col_s <- if (pm$pal_type == "klein") c(0.10, 0.38, 1.05) else if (pm$pal_type == "gold") c(1.0, 0.74, 0.34) else c(1.0, 0.92, 0.80)
        img[1L, near] <- img[1L, near] + (halo + wisp) * col_s[1] + orb * (0.4 * col_s[1] + 0.6)
        img[2L, near] <- img[2L, near] + (halo + wisp) * col_s[2] + orb * (0.4 * col_s[2] + 0.6)
        img[3L, near] <- img[3L, near] + (halo + wisp) * col_s[3] + orb * (0.4 * col_s[3] + 0.6)
      }
      proj_mems[[length(proj_mems) + 1L]] <- list(
        id = pm$id,
        u  = round(mpx / W, 4),
        v  = round(mpy / H_PX, 4),
        w  = round(am$w, 3)
      )
    }
  }

  # Project nearby 3D physical landscape waypoints so ground signposts lock to towns & bluffs!
  proj_wpts <- list()
  for (wp in landscape_waypoints) {
    dz_w <- wp$z - d_pos[3]
    if (dz_w <= 1.2 && dz_w >= -9.5) {
      w_wp <- exp(-0.5 * ((dz_w + 3.2) / 2.8)^2)
      if (w_wp > 0.08) {
        w_scr <- sr_project(matrix(c(wp$x, wp$y, wp$z), nrow = 1),
                            st$lookfrom, st$lookat, st$fov, W, H_PX)
        wu <- w_scr[1, 1] / W; wv <- w_scr[1, 2] / H_PX
        if (wu >= 0.03 && wu <= 0.97 && wv >= 0.18 && wv <= 0.92) {
          proj_wpts[[length(proj_wpts) + 1L]] <- list(
            id = wp$id, u = round(wu, 4), v = round(wv, 4), w = round(w_wp, 3)
          )
        }
      }
    }
  }

  # Gentle fade-in / fade-out at clip ends
  fade <- min(1.0, (t + 0.4) / 2.0) * min(1.0, (RENDER_DUR_S - t + 0.4) / 2.2)
  img <- pmin(pmax(img * fade, 0.0), 1.0)

  list(
    img     = img,
    t       = round(t, 3),
    danny   = round(c(d_scr[1, 1] / W, d_scr[1, 2] / H_PX), 4),
    terrain = terrain_at_z(d_pos[3]),
    mems    = proj_mems,
    wpts    = proj_wpts
  )
}

# ------------------------------------------------------------------------------
# 6. Contact Sheet Mode (--sheet-only) OR Video Stream Render
# ------------------------------------------------------------------------------
write_contact_sheet <- function(frames_list, out_path) {
  cols <- 3L
  rows <- ceiling(length(frames_list) / cols)
  pad  <- 8L
  sheet <- array(0.04, dim = c(rows * H_PX + (rows + 1L) * pad, cols * W + (cols + 1L) * pad, 3L))
  for (i in seq_along(frames_list)) {
    a <- aperm(array(frames_list[[i]]$img, dim = c(3L, W, H_PX)), c(3L, 2L, 1L))
    r0 <- ((i - 1L) %/% cols) * (H_PX + pad) + pad
    c0 <- ((i - 1L) %%  cols) * (W + pad) + pad
    sheet[r0 + seq_len(H_PX), c0 + seq_len(W), ] <- a
  }
  dir.create(dirname(out_path), recursive = TRUE, showWarnings = FALSE)
  writePNG(sheet, out_path)
  cat(sprintf("[walk] Wrote contact sheet -> %s\n", out_path))
}

if (SHEET_ONLY) {
  test_times <- if (HQ_MIN1) c(4, 14, 24, 36, 48, 57) else c(18, 38, 64, 106, 150, 196, 238, 272, 292)
  t_start <- proc.time()[3]
  flist <- lapply(test_times, render_walk_keyframe)
  dt <- proc.time()[3] - t_start
  cat(sprintf("[walk] Rendered %d path-traced sheet frames in %.2fs (%.3fs / frame)\n",
              length(test_times), dt, dt / length(test_times)))
  write_contact_sheet(flist, SHEET_PNG)
  quit(save = "no", status = 0)
}

n_keys <- as.integer(round(RENDER_DUR_S * PT_FPS)) + 1L
key_times <- seq(0.0, RENDER_DUR_S, length.out = n_keys)

if (METADATA_ONLY) {
  cat(sprintf("[walk] Projecting %d timeline keyframes into %s (metadata-only)...\n", n_keys, OUT_JSON))
  project_keyframe_meta <- function(t) {
    st <- danny_state(t)
    d_pos <- st$danny
    d_scr <- sr_project(matrix(c(d_pos[1], d_pos[2] + 0.11, d_pos[3]), nrow = 1),
                        st$lookfrom, st$lookat, st$fov, W, H_PX)
    win_px <- ceiling(44.0 * S_PX)
    proj_mems <- list()
    for (pm in placed_memories) {
      dz <- pm$z - d_pos[3]
      if (dz <= 1.8 && dz >= -10.5) {
        w_mem <- exp(-0.5 * ((dz + 3.0) / 3.1)^2)
        if (w_mem > 0.05) {
          m_scr <- sr_project(matrix(c(pm$x, pm$y + 0.08, pm$z), nrow = 1),
                              st$lookfrom, st$lookat, st$fov, W, H_PX)
          mpx <- m_scr[1, 1]; mpy <- m_scr[1, 2]
          if (mpx >= -win_px && mpx <= W + win_px && mpy >= -win_px && mpy <= H_PX + win_px) {
            proj_mems[[length(proj_mems) + 1L]] <- list(
              id = pm$id, u = round(mpx / W, 4), v = round(mpy / H_PX, 4), w = round(w_mem, 3)
            )
          }
        }
      }
    }
    proj_wpts <- list()
    for (wp in landscape_waypoints) {
      dz_w <- wp$z - d_pos[3]
      if (dz_w <= 1.2 && dz_w >= -9.5) {
        w_wp <- exp(-0.5 * ((dz_w + 3.2) / 2.8)^2)
        if (w_wp > 0.08) {
          w_scr <- sr_project(matrix(c(wp$x, wp$y, wp$z), nrow = 1),
                              st$lookfrom, st$lookat, st$fov, W, H_PX)
          wu <- w_scr[1, 1] / W; wv <- w_scr[1, 2] / H_PX
          if (wu >= 0.03 && wu <= 0.97 && wv >= 0.18 && wv <= 0.92) {
            proj_wpts[[length(proj_wpts) + 1L]] <- list(
              id = wp$id, u = round(wu, 4), v = round(wv, 4), w = round(w_wp, 3)
            )
          }
        }
      }
    }
    list(
      t       = round(t, 3),
      danny   = c(round(d_scr[1, 1] / W, 4), round(d_scr[1, 2] / H_PX, 4)),
      terrain = terrain_at_z(d_pos[3]),
      mems    = proj_mems,
      wpts    = proj_wpts
    )
  }
  timeline_samples <- lapply(key_times, project_keyframe_meta)
  walk_export <- list(
    duration_s     = RENDER_DUR_S,
    full_walk_s    = DURATION_S,
    width          = W,
    height         = H_PX,
    fps            = OUT_FPS,
    video_src      = OUT_MP4,
    note           = "Apple Metal hardware path-traced landscape walk using sonicray + AWS Terrarium DEMs + 4,600 real OpenStreetMap 3D buildings.",
    cantos         = lapply(cantos, function(c) list(
      idx = c$idx, id = c$id, roman = c$roman, era = c$era,
      t0 = c$t0, t1 = c$t1, title = c$title, subtitle = c$subtitle, mems = c$mems
    )),
    waypoints      = lapply(landscape_waypoints, function(wp) list(
      id = wp$id, label = wp$label, sub = wp$sub, lon = wp$lon, lat = wp$lat
    )),
    memories       = lapply(placed_memories, function(pm) list(
      id = pm$id, canto = pm$canto, roman = pm$roman, era = pm$era,
      title = pm$title, place = pm$place, coords = pm$coords, author = pm$author,
      text = pm$text, media = pm$media, pal_type = pm$pal_type
    )),
    timeline       = timeline_samples
  )
  write_json(walk_export, OUT_JSON, auto_unbox = TRUE, digits = 4)
  cat(sprintf("[walk] Wrote enriched metadata -> %s\n", OUT_JSON))
  quit(save = "no", status = 0)
}

cat(sprintf("[walk] Rendering %d Metal path-traced keyframes -> %d frames @ %d fps (%s)...\n",
            n_keys, (n_keys - 1L) * SUBFRAMES, OUT_FPS, OUT_MP4))

ff <- Sys.which("ffmpeg")
stopifnot(nzchar(ff))
dir.create(dirname(OUT_MP4), recursive = TRUE, showWarnings = FALSE)

crf_val <- if (HQ_MIN1) 17L else 21L
preset_val <- if (HQ_MIN1) "fast" else "veryfast"
ff_cmd <- paste(
  shQuote(ff), "-y -loglevel error",
  "-f rawvideo -pix_fmt rgb24",
  sprintf("-s %dx%d -r %d", W, H_PX, OUT_FPS),
  "-i -",
  sprintf("-c:v libx264 -preset %s -crf %d -pix_fmt yuv420p -movflags +faststart", preset_val, crf_val),
  shQuote(OUT_MP4)
)
pipe_con <- pipe(ff_cmd, open = "wb")

timeline_samples <- vector("list", n_keys)
n_sheet_panels <- if (HQ_MIN1) 6L else 9L
sheet_keep_idx <- round(seq(max(2L, round(n_keys * 0.05)), max(3L, n_keys - 4L), length.out = n_sheet_panels))
sheet_frames <- list()

t_render0 <- proc.time()[3]
prev_kf <- render_walk_keyframe(key_times[1])
timeline_samples[[1]] <- list(t = prev_kf$t, danny = prev_kf$danny, terrain = prev_kf$terrain, mems = prev_kf$mems, wpts = prev_kf$wpts)

for (k in 2:n_keys) {
  curr_kf <- render_walk_keyframe(key_times[k])
  timeline_samples[[k]] <- list(t = curr_kf$t, danny = curr_kf$danny, terrain = curr_kf$terrain, mems = curr_kf$mems, wpts = curr_kf$wpts)
  if (k %in% sheet_keep_idx) sheet_frames[[length(sheet_frames) + 1L]] <- curr_kf

  for (s in seq_len(SUBFRAMES) - 1L) {
    alpha <- s / SUBFRAMES
    blended <- (1.0 - alpha) * prev_kf$img + alpha * curr_kf$img
    raw_u8 <- as.raw(as.integer(blended * 255.0 + 0.5))
    writeBin(raw_u8, pipe_con)
  }
  prev_kf <- curr_kf

  step_log <- if (HQ_MIN1) 30L else 90L
  if (k %% step_log == 0L || k == n_keys) {
    el <- proc.time()[3] - t_render0
    pct <- 100.0 * k / n_keys
    cat(sprintf("  [%5.1f%%] keyframe %d/%d (t=%.1fs) | elapsed %.1fs\n", pct, k, n_keys, key_times[k], el))
  }
}
close(pipe_con)

write_contact_sheet(sheet_frames, SHEET_PNG)

walk_export <- list(
  duration_s     = RENDER_DUR_S,
  full_walk_s    = DURATION_S,
  width          = W,
  height         = H_PX,
  fps            = OUT_FPS,
  video_src      = OUT_MP4,
  note           = "Apple Metal hardware path-traced landscape walk using sonicray + AWS Terrarium DEMs + 4,600 real OpenStreetMap 3D buildings.",
  cantos         = lapply(cantos, function(c) list(
    idx = c$idx, id = c$id, roman = c$roman, era = c$era,
    t0 = c$t0, t1 = c$t1, title = c$title, subtitle = c$subtitle, mems = c$mems
  )),
  waypoints      = lapply(landscape_waypoints, function(wp) list(
    id = wp$id, label = wp$label, sub = wp$sub, lon = wp$lon, lat = wp$lat
  )),
  memories       = lapply(placed_memories, function(pm) list(
    id = pm$id, canto = pm$canto, roman = pm$roman, era = pm$era,
    title = pm$title, place = pm$place, coords = pm$coords, author = pm$author,
    text = pm$text, media = pm$media, pal_type = pm$pal_type
  )),
  timeline       = timeline_samples
)
write_json(walk_export, OUT_JSON, auto_unbox = TRUE, digits = 4)
cat(sprintf("[walk] Done! Video: %s | Metadata: %s\n", OUT_MP4, OUT_JSON))
