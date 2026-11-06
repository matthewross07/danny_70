#!/usr/bin/env Rscript
# ==============================================================================
# scripts/push_to_google_sheet.R
# Writes all supplemental photo pairings (Elk Hunt 2015, When He Asked Debbie,
# Sint Maarten, Mountain Cabin) AND the 12 folder/text memories (Marie/Theo/Lina
# France & Italy 2011-2025, Ryan's Colorado backcountry photos, Seanor's Ouray
# photo) directly back into Danny's Google Sheet using `googlesheets4`.
#
# Run once from RStudio or terminal (will open a 1-click Google OAuth tab if needed):
#   Rscript scripts/push_to_google_sheet.R
# ==============================================================================

suppressPackageStartupMessages({
  library(googlesheets4)
  library(jsonlite)
})

# Enable interactive browser OAuth even when invoked via `Rscript`
options(rlang_interactive = TRUE)
gs4_auth(email = "matthew.r.v.ross@gmail.com")

payload <- fromJSON("data/google_sheet_sync_payload.json", simplifyVector = FALSE)
ss <- payload$sheet_id
sheet_info <- gs4_get(ss)
tab_name <- sheet_info$sheets$name[[1]]
cat(sprintf("[sheet] Connected to '%s' (tab: '%s')\n", sheet_info$name, tab_name))

# 1. Update Column D on existing rows (25: Debbie, 29: Sint Maarten, 34: Cabin, 36: Elk Hunt 2015)
for (u in payload$row_updates) {
  cell_range <- sprintf("D%d", u$sheet_row)
  range_write(
    ss = ss,
    data = data.frame(media = u$media_col_d, stringsAsFactors = FALSE),
    sheet = tab_name,
    range = cell_range,
    col_names = FALSE,
    reformat = FALSE
  )
  cat(sprintf("  Updated %s (form row %d) with paired Drive media links.\n", cell_range, u$form_row))
}

# 2. Read existing Column D to avoid duplicating any already-appended rows
existing <- read_sheet(ss, sheet = tab_name, col_types = "c")
existing_col_d <- if (ncol(existing) >= 4) paste(existing[[4]], collapse = " ") else ""

to_append <- list()
for (r in payload$append_rows) {
  # Check first Drive file ID so re-running is 100% idempotent
  first_id <- sub(".*id=([A-Za-z0-9_-]+).*", "\\1", r$media)
  if (nzchar(first_id) && grepl(first_id, existing_col_d, fixed = TRUE)) {
    cat(sprintf("  Skipping %s (already present in Google Sheet).\n", r$id))
    next
  }
  to_append[[length(to_append) + 1L]] <- data.frame(
    a = r$timestamp,
    b = r$description,
    c = r$location,
    d = r$media,
    stringsAsFactors = FALSE
  )
}

if (length(to_append) > 0) {
  df_new <- do.call(rbind, to_append)
  sheet_append(ss = ss, data = df_new, sheet = tab_name)
  cat(sprintf("[sheet] Appended %d new memories (Marie/Euro, Ryan, Seanor) to Google Sheet!\n", nrow(df_new)))
} else {
  cat("[sheet] All extra memories are already present in the Google Sheet.\n")
}
