"""""Single shared design-token source of truth for The Gold Panicles QR Attendance System."""

STYLESHEET_RELATIVE_PATH = "src/ui/styles/theme.qss"


class Colors:
    """Design palette tokens.

    Theme: Minimal Editorial Publication
    Color Scheme:
      --text: #040316;
      --background: #fbfbfe;
      --primary: #ece3da;
      --secondary: #eee6e2;
      --accent: #0c0f18;
    """
    # Core User-Defined Palette
    TEXT = "#040316"
    BACKGROUND = "#FBFBFE"
    PRIMARY = "#ECE3DA"
    SECONDARY = "#EEE6E2"
    ACCENT = "#0C0F18"

    # Surface & Canvas Mapping
    CANVAS = BACKGROUND
    SURFACE = PRIMARY
    SURFACE_ALT = SECONDARY
    BORDER = "#DDD5CE"
    BORDER_STRONG = "#C8BFB7"
    BORDER_HOVER = ACCENT

    ELEVATION_0 = CANVAS
    ELEVATION_1 = SURFACE
    ELEVATION_2 = SURFACE_ALT

    # Text hierarchy
    TEXT_PRIMARY = TEXT
    TEXT_MUTED = "#6B6775"
    TEXT_SECONDARY = "#504C5A"

    # Accent tokens (Clean charcoal-black accent)
    ACCENT_DARK = ACCENT
    ACCENT_GOLD = ACCENT              # Kept for backward-compatibility with existing references
    ACCENT_GOLD_HOVER = "#242A38"
    ACCENT_GOLD_PRESSED = "#040316"

    # Refined Semantic & Status Colors (Crisp, minimal, high-contrast on light surfaces)
    STATUS_OVERDUE_BG = "#FCE8E6"
    STATUS_OVERDUE = "#A51D24"
    STATUS_OVERDUE_BORDER = "#F5C2C7"

    STATUS_COMPLETED_BG = "#E8F0FE"
    STATUS_COMPLETED = "#1A56DB"
    STATUS_COMPLETED_BORDER = "#B8D5F8"

    STATUS_OPEN_BG = "#E6F4EA"
    STATUS_OPEN = "#0F6D38"
    STATUS_OPEN_BORDER = "#B7E1CD"

    STATUS_RESOLVED_BG = "#FEF7E0"
    STATUS_RESOLVED = "#8F5800"
    STATUS_RESOLVED_BORDER = "#FCE293"

    SUCCESS_BG = STATUS_OPEN_BG
    SUCCESS_BORDER = STATUS_OPEN_BORDER
    INFO_BG = STATUS_COMPLETED_BG
    INFO_BORDER = STATUS_COMPLETED_BORDER
    DANGER_BG = STATUS_OVERDUE_BG
    DANGER_BORDER = STATUS_OVERDUE_BORDER
    WARNING_BG = STATUS_RESOLVED_BG
    WARNING_BORDER = STATUS_RESOLVED_BORDER

    CHIP_DUTY_BG = PRIMARY
    CHIP_NEUTRAL_BG = SECONDARY

    FLASH_SUCCESS = "rgba(15, 109, 56, 0.20)"
    FLASH_FAILURE = "rgba(165, 29, 36, 0.20)"
    DANGER_SOLID = "#C5221F"

    CALENDAR_SELECTED_BG = ACCENT
    CALENDAR_SELECTED_TEXT = "#FBFBFE"

    TONAL_GOLD_BG = SECONDARY
    TONAL_GOLD_BORDER = BORDER
    TONAL_GOLD_TEXT = TEXT


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
    DIALOG_HEADER_DANGER = "dialogHeaderDanger"


class Spacing:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


class Radius:
    SUPER = 8
    SHARP = 4
    XS = 2
    SM = 6


class Motion:
    FAST_MS = 150
    STANDARD_MS = 250
    SLOW_MS = 400


class Typography:
    DISPLAY_FAMILY = "M Ying Hei PRC W5"
    BODY_FAMILY = "Helvetica Neue"
    BODY_FAMILY_FALLBACK = "Helvetica"
    DATA_GRID_PT = 11
    LABEL_PT = 12
    BODY_PT = 13
