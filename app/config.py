from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    app_name: str = "INFERIO VPN"
    bot_token: str = ""
    admin_ids: str = ""
    public_base_url: str = ""
    database_url: str = ""
    timezone: str = "Europe/Berlin"
    support_username: str = "@inferio_support"
    terms_text: str = "Пользовательское соглашение не заполнено."
    privacy_text: str = "Политика конфиденциальности не заполнена."
    terms_version: str = "1.0"
    privacy_version: str = "1.0"
    platega_api_base: str = "https://app.platega.io"
    platega_merchant_id: str = ""
    platega_secret: str = ""
    platega_return_url: str = ""
    platega_callback_url: str = ""
    remnawave_base_url: str = ""
    remnawave_token: str = ""
    remnawave_api_prefix: str = "/api"
    trial_enabled: bool = True
    trial_days: int = 3
    trial_squad_uuids: str = ""
    grace_enabled: bool = False
    grace_squad_uuid: str = ""
    grace_hours: int = 24
    reminder_days: str = "7,3,1,0"
    referral_reward_days: int = 7
    referral_require_purchase: bool = True
    partner_default_commission: float = 20
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    @property
    def admin_id_set(self): return {int(x.strip()) for x in self.admin_ids.split(',') if x.strip().isdigit()}
    @property
    def trial_squads(self): return [x.strip() for x in self.trial_squad_uuids.split(',') if x.strip()]
    @property
    def reminder_day_set(self): return [int(x.strip()) for x in self.reminder_days.split(',') if x.strip().isdigit()]
settings=Settings()
