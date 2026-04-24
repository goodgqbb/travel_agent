import yaml
import os

class ConfigManager:
    _config = None

    @classmethod
    def get_config(cls):
        if cls._config is None:
            # 读取项目根目录下的 config.yaml
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config\\settings.yaml')
            with open(config_path, 'r', encoding='utf-8') as f:
                cls._config = yaml.safe_load(f)
        return cls._config

# 对外暴露一个配置字典
app_config = ConfigManager.get_config()