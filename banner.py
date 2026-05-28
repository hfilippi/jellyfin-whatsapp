from logger_colors import LogColor

def print_startup_banner(app_name, app_version):
    banner = r"""
   _      _ _        __ _                     _           _                   
  (_) ___| | |_   _ / _(_)_ __      __      _| |__   __ _| |_ ___  __ _ _ __  
  | |/ _ \ | | | | | |_| | '_ \ ____\ \ /\ / / '_ \ / _` | __/ __|/ _` | '_ \ 
  | |  __/ | | |_| |  _| | | | |_____\ V  V /| | | | (_| | |_\__ \ (_| | |_) |
 _/ |\___|_|_|\__, |_| |_|_| |_|      \_/\_/ |_| |_|\__,_|\__|___/\__,_| .__/ 
|__/          |___/                                                    |_|    
    """
    print(f"{LogColor.MAGENTA}{banner}{LogColor.RESET}")
    print(f"{LogColor.CYAN}🎬 {app_name} v{app_version}{LogColor.RESET}")
    print()