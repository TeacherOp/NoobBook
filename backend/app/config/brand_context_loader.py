"""
Brand Context Loader - Builds brand context for studio agent prompts.

Educational Note: This module creates formatted brand guidelines context
that can be injected into studio agent system prompts. The context includes:

1. Color Palette - Primary, secondary, accent, and custom colors
2. Typography - Font families and sizing information
3. Brand Guidelines - Written guidelines and best practices
4. Brand Voice - Tone, personality, and keywords

Brand config is now user-level (workspace setting). Studio agents pass
project_id, which is resolved to user_id here — so agents need zero changes.
"""
import logging
from typing import Dict, Any, List, Optional

from app.services.data_services.brand_config_service import brand_config_service
from app.services.data_services.brand_asset_service import brand_asset_service

logger = logging.getLogger(__name__)


class BrandContextLoader:
    """
    Loader for building brand context for studio agent prompts.

    Educational Note: This loader is called by studio services before
    content generation. It checks if brand is enabled for the feature
    and builds formatted context for the AI to follow.

    Studio agents pass project_id → we resolve to user_id internally,
    since brand config is now a workspace-level (per-user) setting.
    """

    def _resolve_user_id(self, project_id: str) -> Optional[str]:
        """
        Resolve project_id to user_id via the projects table.

        Educational Note: Brand moved from project-level to user-level,
        but studio agents still pass project_id. This bridge method
        ensures backward compatibility with zero changes to agents.

        Uses ``get_project_owner_id`` (lookup by id only) rather than
        ``get_project`` — the latter is user-scoped (``WHERE id = ? AND
        user_id = ?``) and falls back to ``DEFAULT_USER_ID`` when no
        user_id is passed. Studio background jobs (presentation,
        business_report, blog, etc.) call this helper WITHOUT a
        user_id, so the user-scoped lookup silently returned None for
        any project not owned by DEFAULT_USER_ID — every Studio job on
        such projects was running with brand styling stripped, and the
        only signal was the "could not resolve user_id" warning.

        Args:
            project_id: The project UUID

        Returns:
            The user_id who owns the project, or None if not found
        """
        from app.services.data_services import project_service
        return project_service.get_project_owner_id(project_id)

    def load_brand_context(
        self,
        project_id: str,
        feature_name: str,
        user_id: str = None
    ) -> str:
        """
        Load brand context for injection into a studio agent prompt.

        Educational Note: This method first checks if the feature has
        brand enabled. If not, it returns an empty string. This allows
        features like mind maps to skip brand application while
        presentations and blogs follow brand guidelines.

        Args:
            project_id: The project UUID (used as fallback to resolve user_id)
            feature_name: The studio feature name (e.g., 'blog', 'presentation')
            user_id: Optional user UUID — skips project lookup when provided

        Returns:
            Formatted brand context string, or empty string if brand disabled
        """
        # Use provided user_id, or resolve from project_id (brand is user-level)
        if not user_id:
            user_id = self._resolve_user_id(project_id)
        if not user_id:
            logger.warning("Brand context skipped: could not resolve user_id (project=%s)", project_id[:8])
            return ""

        # Check if brand is enabled for this feature
        if not brand_config_service.is_feature_enabled(user_id, feature_name):
            logger.info("Brand context skipped: feature '%s' disabled (user=%s)", feature_name, user_id[:8])
            return ""

        # Get brand config
        config = brand_config_service.get_config(user_id)

        # Build context sections, tracking which parts are present
        sections = []
        included_parts = []

        sections.append("## Brand Guidelines")
        sections.append("")

        # Add color palette
        color_context = self._build_color_context(config)
        if color_context:
            sections.append(color_context)
            included_parts.append("colors")

        # Add typography
        typography_context = self._build_typography_context(config)
        if typography_context:
            sections.append(typography_context)
            included_parts.append("typography")

        # Add brand assets info
        assets_context = self._build_assets_context(user_id)
        if assets_context:
            sections.append(assets_context)
            included_parts.append("assets")

        # Add brand voice
        voice_context = self._build_voice_context(config)
        if voice_context:
            sections.append(voice_context)
            included_parts.append("voice")

        # Add guidelines text
        guidelines_context = self._build_guidelines_context(config)
        if guidelines_context:
            sections.append(guidelines_context)
            included_parts.append("guidelines")

        # Add long-form design.md spec — this is the big one. When admins fill
        # this out, it carries layout/component/voice rules the structured
        # tokens above can't express. Skipped silently when empty so existing
        # workspaces aren't penalized.
        design_md_context = self._build_design_md_context(config)
        if design_md_context:
            sections.append(design_md_context)
            included_parts.append("design_md")

        # Add best practices
        practices_context = self._build_practices_context(config)
        if practices_context:
            sections.append(practices_context)
            included_parts.append("practices")

        if len(sections) <= 2:  # Only header and empty line
            logger.info("Brand context empty: no sections have content (user=%s, feature=%s)", user_id[:8], feature_name)
            return ""

        sections.append("**MANDATORY**: All generated content MUST use these exact brand colors, fonts, voice, and logo. Do NOT substitute with defaults or generic values.")
        sections.append("")

        context = "\n".join(sections)
        logger.info("Brand context loaded: feature=%s, user=%s, sections=[%s], length=%d chars",
                     feature_name, user_id[:8], ", ".join(included_parts), len(context))
        return context

    def _build_color_context(self, config: Dict[str, Any]) -> str:
        """Build color palette context section, respecting per-color enabled toggles."""
        colors = config.get("colors", {})

        if not colors:
            return ""

        # Per-color enabled flags — default all-on for backward compatibility
        enabled = colors.get("enabled", {})

        lines = [
            "### Color Palette",
            "",
        ]

        # Standard colors with usage mapping so agents know where to apply each
        # Only include colors the user has enabled in Settings > Design > Colors
        if colors.get("primary") and enabled.get("primary", True):
            lines.append(f"- **Primary Color**: {colors['primary']} → Use for: headers, section backgrounds, key accents")
        if colors.get("accent") and enabled.get("accent", True):
            lines.append(f"- **Accent Color**: {colors['accent']} → Use for: CTA buttons, links, highlights")
        if colors.get("secondary") and enabled.get("secondary", True):
            lines.append(f"- **Secondary Color**: {colors['secondary']} → Use for: secondary sections, borders, dividers")
        if colors.get("background") and enabled.get("background", True):
            lines.append(f"- **Background Color**: {colors['background']} → Use for: email/page body background")
        if colors.get("text") and enabled.get("text", True):
            lines.append(f"- **Text Color**: {colors['text']} → Use for: all body text, paragraphs")

        # Custom colors
        custom_colors = colors.get("custom", [])
        if custom_colors:
            lines.append("")
            lines.append("**Custom Colors**:")
            for custom in custom_colors:
                name = custom.get("name", "Unnamed")
                value = custom.get("value", "#000000")
                lines.append(f"- {name}: {value}")

        lines.append("")
        return "\n".join(lines)

    def _build_typography_context(self, config: Dict[str, Any]) -> str:
        """Build typography context section."""
        typography = config.get("typography", {})

        if not typography:
            return ""

        lines = [
            "### Typography",
            "",
        ]

        # Include CSS-ready snippets so agents can copy-paste directly
        if typography.get("heading_font"):
            hf = typography['heading_font']
            lines.append(f"- **Heading Font**: {hf} → CSS: font-family: '{hf}', serif;")
        if typography.get("body_font"):
            bf = typography['body_font']
            lines.append(f"- **Body Font**: {bf} → CSS: font-family: '{bf}', sans-serif;")

        # Google Fonts link for web/email use
        fonts_to_import = []
        if typography.get("body_font"):
            fonts_to_import.append(typography["body_font"])
        if typography.get("heading_font"):
            fonts_to_import.append(typography["heading_font"])
        if fonts_to_import:
            families = "&family=".join(f.replace(" ", "+") + ":wght@400;700" for f in fonts_to_import)
            lines.append(f"- **Google Fonts**: `<link href=\"https://fonts.googleapis.com/css2?family={families}&display=swap\" rel=\"stylesheet\">`")

        if typography.get("heading_weight"):
            lines.append(f"- **Heading Weight**: {typography['heading_weight']}")
        if typography.get("body_weight"):
            lines.append(f"- **Body Weight**: {typography['body_weight']}")

        heading_sizes = typography.get("heading_sizes", {})
        if heading_sizes:
            sizes = [f"H{i}={heading_sizes.get(f'h{i}', 'auto')}" for i in range(1, 7) if heading_sizes.get(f'h{i}')]
            lines.append(f"- **Heading Sizes**: {', '.join(sizes)}")

        if typography.get("body_size"):
            lines.append(f"- **Body Size**: {typography['body_size']}")
        if typography.get("line_height"):
            lines.append(f"- **Line Height**: {typography['line_height']}")

        lines.append("")
        return "\n".join(lines)

    def _build_assets_context(self, user_id: str) -> str:
        """Build brand assets context section."""
        assets = brand_asset_service.list_assets(user_id)

        if not assets:
            return ""

        # Group by type
        logos = [a for a in assets if a.get("asset_type") == "logo"]
        icons = [a for a in assets if a.get("asset_type") == "icon"]

        lines = [
            "### Brand Assets",
            "",
        ]

        # Primary logo
        primary_logo = next((a for a in logos if a.get("is_primary")), None)
        if primary_logo:
            lines.append(f"- **Primary Logo**: {primary_logo.get('name', 'Logo')}")
            if primary_logo.get("description"):
                lines.append(f"  - Description: {primary_logo['description']}")
            lines.append("- **Logo Placeholder**: Use `BRAND_LOGO` as the image src in HTML templates")

        # Logo count
        if len(logos) > 1:
            lines.append(f"- **Additional Logos Available**: {len(logos) - 1}")

        # Icons — list each by name so the AI knows what's available
        if icons:
            lines.append(f"- **Icons Available**: {len(icons)}")
            for icon in icons:
                primary_tag = " (primary)" if icon.get("is_primary") else ""
                desc = f" — {icon['description']}" if icon.get("description") else ""
                lines.append(f"  - {icon.get('name', 'Icon')}{primary_tag}{desc}")

        lines.append("")
        return "\n".join(lines)

    def _build_voice_context(self, config: Dict[str, Any]) -> str:
        """Build brand voice context section."""
        voice = config.get("voice", {})

        if not voice:
            return ""

        lines = [
            "### Brand Voice",
            "",
        ]

        if voice.get("tone"):
            lines.append(f"- **Tone**: {voice['tone']}")

        personality = voice.get("personality", [])
        if personality:
            lines.append(f"- **Personality Traits**: {', '.join(personality)}")

        keywords = voice.get("keywords", [])
        if keywords:
            lines.append(f"- **Key Terms to Use**: {', '.join(keywords)}")

        lines.append("")
        return "\n".join(lines)

    def _build_design_md_context(self, config: Dict[str, Any]) -> str:
        """Build the long-form design.md spec section."""
        design_md = (config.get("design_md") or "").strip()
        if not design_md:
            return ""

        return "\n".join([
            "### Design Specification",
            "",
            design_md,
            "",
        ])

    def _build_guidelines_context(self, config: Dict[str, Any]) -> str:
        """Build written guidelines context section."""
        guidelines = config.get("guidelines")

        if not guidelines:
            return ""

        lines = [
            "### Written Guidelines",
            "",
            guidelines,
            "",
        ]

        return "\n".join(lines)

    def _build_practices_context(self, config: Dict[str, Any]) -> str:
        """Build best practices (dos/donts) context section."""
        practices = config.get("best_practices", {})

        dos = practices.get("dos", [])
        donts = practices.get("donts", [])

        if not dos and not donts:
            return ""

        lines = [
            "### Best Practices",
            "",
        ]

        if dos:
            lines.append("**Do**:")
            for item in dos:
                lines.append(f"- {item}")
            lines.append("")

        if donts:
            lines.append("**Don't**:")
            for item in donts:
                lines.append(f"- {item}")
            lines.append("")

        return "\n".join(lines)

    def build_image_prompt_prefix(
        self,
        user_id: Optional[str],
        feature_name: str,
    ) -> str:
        """
        Compact brand block tuned for image-generation prompts.

        The full `load_brand_context` builds a multi-section markdown block
        meant for Claude system prompts (~2-3k chars). GPT Image 2 image
        prompts work better with one tight sentence, so this returns
        something like:

            "Brand style: amber/cream palette (primary #D97706, accent
            #F59E0B), warm friendly tone."

        Returns "" when brand isn't configured or the feature has brand
        disabled — callers should pass the user's direction unprefixed in
        that case.
        """
        if not user_id:
            return ""
        if not brand_config_service.is_feature_enabled(user_id, feature_name):
            return ""

        config = brand_config_service.get_config(user_id) or {}
        colors = config.get("colors", {}) or {}
        typography = config.get("typography", {}) or {}
        voice = config.get("voice", {}) or {}

        bits: List[str] = []

        # Color palette — only the primary + accent. Listing every color
        # tends to over-constrain the model and produces muddy outputs.
        primary = colors.get("primary")
        accent = colors.get("accent")
        if primary or accent:
            color_parts = []
            if primary:
                color_parts.append(f"primary {primary}")
            if accent:
                color_parts.append(f"accent {accent}")
            bits.append("colors " + ", ".join(color_parts))

        # Tone — single descriptor only. Long voice descriptions confuse
        # the image model far more than they help.
        tone = (voice.get("tone") or "").strip()
        if tone:
            bits.append(f"{tone} tone")

        # Heading font — useful when the image contains text (ads,
        # infographics with labels). Body font almost never appears in
        # images so we skip it.
        heading_font = (typography.get("heading_font") or "").strip()
        if heading_font:
            bits.append(f"{heading_font} headings")

        if not bits:
            return ""

        return f"Brand style: {'; '.join(bits)}."

    def get_brand_summary(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of brand configuration for display purposes.

        Args:
            user_id: The user UUID

        Returns:
            Summary dict with key brand elements, or None if no config
        """
        config = brand_config_service.get_config(user_id)
        assets = brand_asset_service.list_assets(user_id)

        # Get primary logo
        primary_logo = next(
            (a for a in assets if a.get("asset_type") == "logo" and a.get("is_primary")),
            None
        )

        colors = config.get("colors", {})
        typography = config.get("typography", {})
        voice = config.get("voice", {})

        return {
            "primary_color": colors.get("primary"),
            "secondary_color": colors.get("secondary"),
            "accent_color": colors.get("accent"),
            "heading_font": typography.get("heading_font"),
            "body_font": typography.get("body_font"),
            "tone": voice.get("tone"),
            "primary_logo_name": primary_logo.get("name") if primary_logo else None,
            "has_guidelines": bool(config.get("guidelines")),
            "asset_count": len(assets),
            "feature_settings": config.get("feature_settings", {})
        }


# Singleton instance
brand_context_loader = BrandContextLoader()


def load_brand_context(project_id: str, feature_name: str, user_id: str = None) -> str:
    """
    Convenience function for loading brand context.

    Educational Note: Studio agents call this with project_id. The loader
    resolves project_id → user_id internally since brand is now user-level.
    When user_id is provided directly, the project lookup is skipped.

    Args:
        project_id: The project UUID
        feature_name: The studio feature name
        user_id: Optional user UUID — skips project lookup when provided

    Returns:
        Formatted brand context string
    """
    return brand_context_loader.load_brand_context(project_id, feature_name, user_id=user_id)
