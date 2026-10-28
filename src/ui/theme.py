"""""Single shared design-token source of truth for The Gold Panicles QR Attendance System."""

STYLESHEET_RELATIVE_PATH = "src/ui/styles/theme.qss"


class Colors:
    CANVAS = "#0B0B0C"
    SURFACE = "#141416"
    BORDER = "#222226"
    BORDER_STRONG = "#24242A"
    BORDER_HOVER = "#33333A"

    ELEVATION_0 = CANVAS
    ELEVATION_1 = SURFACE
    ELEVATION_2 = "#1B1B1F"

    TEXT_PRIMARY = "#F4EFEA"
    TEXT_MUTED = "#8E8E93"
    TEXT_SECONDARY = "#A1A1AA"

    ACCENT_GOLD = "#DAA520"
    ACCENT_GOLD_HOVER = "#E5B842"
    ACCENT_GOLD_PRESSED = "#B8860B"

    STATUS_OVERDUE_BG = "#58111A"
    STATUS_OVERDUE = "#FF99A4"
    STATUS_OVERDUE_BORDER = "#7A1B28"

    STATUS_COMPLETED_BG = "#122B3D"
    STATUS_COMPLETED = "#80C8FF"
    STATUS_COMPLETED_BORDER = "#1C3D54"

    # FIXED THIS SESSION: STATUS_OPEN_* previously aliased directly to
    # STATUS_COMPLETED_* (STATUS_OPEN_BG = STATUS_COMPLETED_BG, etc.), which
    # meant the live attendance board rendered OPEN ("still in the office")
    # and COMPLETED ("already checked out") status pills as pixel-identical
    # blue badges -- no color cue distinguished the two most important states
    # on the board's single busiest column. Given its own distinct hue
    # entirely (green, conventionally "currently active"), built with the
    # same dark-bg / light-pastel-text / mid-saturation-border construction
    # used by every other status triplet here, so it can never collide with
    # OVERDUE (red), COMPLETED (blue), or RESOLVED (gold-brown) again.
    STATUS_OPEN_BG = "#113B24"
    STATUS_OPEN = "#8FE3B0"
    STATUS_OPEN_BORDER = "#1E5A38"

    STATUS_RESOLVED_BG = "#3A2E12"
    STATUS_RESOLVED = "#D9B872"
    STATUS_RESOLVED_BORDER = "#4E3E1A"

    # NOTE: SUCCESS_BG/SUCCESS_BORDER now resolve to the new green OPEN
    # colors rather than the old blue COMPLETED colors, as a direct
    # consequence of the fix above. This is flagged as a net improvement,
    # not a regression -- green is the more conventional semantic for a
    # "success" state than blue was -- but noted in case green appears
    # somewhere unexpected that was relying on the old blue value.
    SUCCESS_BG = STATUS_OPEN_BG
    SUCCESS_BORDER = STATUS_OPEN_BORDER
    INFO_BG = STATUS_COMPLETED_BG
    INFO_BORDER = STATUS_COMPLETED_BORDER
    DANGER_BG = STATUS_OVERDUE_BG
    DANGER_BORDER = STATUS_OVERDUE_BORDER
    WARNING_BG = STATUS_RESOLVED_BG
    WARNING_BORDER = STATUS_RESOLVED_BORDER

    CHIP_DUTY_BG = "#2E2512"
    CHIP_NEUTRAL_BG = ELEVATION_2

    FLASH_SUCCESS = "rgba(218, 165, 32, 0.2)"
    FLASH_FAILURE = "rgba(255, 90, 90, 0.18)"
    DANGER_SOLID = "#C62828"

    CALENDAR_SELECTED_BG = ACCENT_GOLD
    CALENDAR_SELECTED_TEXT = "#0B0B0C"

    TONAL_GOLD_BG = "#2E2512"
    TONAL_GOLD_BORDER = "rgba(218, 165, 32, 0.35)"
    TONAL_GOLD_TEXT = ACCENT_GOLD_HOVER


class ObjectNames:
    BTN_CHROME = "btn_chrome"
    BTN_TONAL = "btn_tonal"
    CARD_SURFACE = "cardSurface"
    EMPTY_STATE_LABEL = "emptyStateLabel"
    CAMERA_STATUS_LABEL = "cameraStatusLabel"
    CAMERA_FEED_LABEL = "cameraFeedLabel"
    CAMERA_COUNT_FRAME = "cameraCountFrame"
    FORM_MODE_CREATE = "formModeCreate"
    FORM_MODE_EDIT = "formModeEdit"
    BADGE_ACTIVE = "badge_active"
    BADGE_INACTIVE = "badge_inactive"

    MAIN_HEADER_FRAME = "mainHeaderFrame"
    BRAND_TITLE = "brandHeader"
    LIVE_CLOCK = "liveClockLabel"
    BTN_CHROME_DANGER = "btn_chrome_danger"
    ADMIN_USER_BADGE = "adminUserBadge"

    CARD_SUPER = "cardSuper"
    GP_SUPER_INPUT = "gpSuperInput"
    VERIFICATION_CARD = "verificationCard"
    BTN_MACRO = "btn_macro"
    SEARCH_INPUT = "searchInput"
    FILTER_PILL = "filterPill"
    TEXT_MUTED = "textMuted"
    TEXT_SECONDARY = "textSecondary"

    # --- Restored this session: flagged by an external code-review pass
    # as referenced by admin-dashboard/dialog files (admin_login.py,
    # shutdown_dialog.py, modals.py, and the admin tab modules) but
    # missing from this class, which would raise AttributeError on
    # construction of every one of those screens. Mapped against the
    # real theme.qss selectors reviewed earlier this session; not
    # re-verified against theme.qss in this exact turn (see chat caveat)
    # pending a re-paste to close the loop fully. Button-style names use
    # this file's existing snake_case convention (matching btn_chrome/
    # btn_tonal/btn_macro); everything else uses the existing camelCase
    # convention (matching brandHeader/liveClockLabel/adminUserBadge).
    BTN_PRIMARY = "btn_primary"
    BTN_CANCEL = "btn_cancel"
    BTN_DANGER_SOLID = "btn_danger_solid"
    BTN_ROW_EDIT = "btn_row_edit"
    BTN_ROW_DELETE = "btn_row_delete"
    BTN_ROW_WARNING = "btn_row_warning"
    BTN_ROW_SUCCESS = "btn_row_success"

    SECTION_TITLE = "sectionTitle"
    SECTION_TITLE_DANGER = "sectionTitleDanger"
    SURFACE_CARD = "surfaceCard"
    HEADING_SECTION = "headingSection"
    STAT_CARD = "statCard"
    STAT_CARD_TITLE = "statCardTitle"
    STAT_CARD_VALUE = "statCardValue"
    FORM_LABEL = "formLabel"
    FORM_ERROR_LABEL = "formErrorLabel"
    DIALOG_SUBJECT_NAME = "dialogSubjectName"
    DIALOG_EMPHASIS_TEXT = "dialogEmphasisText"
    DIALOG_HEADER_INFO = "dialogHeaderInfo"
    INFO_CHIP_GOLD = "infoChipGold"

    # Not in the external audit's explicit list of 20, but added
    # proactively: theme.qss (per this session's earlier review) defines
    # a #dialogHeaderDanger rule as the direct sibling of the now-restored
    # #dialogHeaderInfo, and it would be a near-certain miss otherwise.
    # Flagging rather than silently assuming it's definitely referenced
    # anywhere — please confirm against the real dialog files.
    DIALOG_HEADER_DANGER = "dialogHeaderDanger"


class Spacing:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


class Radius:
    SUPER = 28
    SHARP = 4
    XS = 2
    SM = 6


class Motion:
    FAST_MS = 150
    STANDARD_MS = 250
    SLOW_MS = 400


class Typography:
    DISPLAY_FAMILY = "Degular Display"
    BODY_FAMILY = "Helvetica Neue"
    BODY_FAMILY_FALLBACK = "Arial"
    DATA_GRID_PT = 11
    LABEL_PT = 12
    BODY_PT = 13