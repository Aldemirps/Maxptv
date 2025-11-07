#!/usr/bin/env python3
"""
Web to APK - Termux Edition
Usa serviços cloud para buildar APK no Termux
"""

import os
import json
import requests
import tempfile
from pathlib import Path

class TermuxWebToAPK:
    def __init__(self):
        self.temp_dir = None
        
    def check_termux(self):
        """Verifica se está no Termux"""
        return os.path.exists("/data/data/com.termux")
    
    def install_termux_deps(self):
        """Instala dependências do Termux"""
        print("📦 Instalando dependências Termux...")
        
        commands = [
            "pkg update && pkg upgrade -y",
            "pkg install python git curl wget zip unzip -y",
            "pkg install openjdk-17 -y",
            "pip install requests"
        ]
        
        for cmd in commands:
            print(f"Executando: {cmd}")
            os.system(cmd)
    
    def use_cloud_service(self, url, app_name):
        """Usa serviço cloud para buildar APK"""
        print("☁️ Usando serviço cloud...")
        
        # APIs disponíveis para Termux
        services = {
            "appsgeyser": {
                "url": "https://appsgeyser.com/api/create/",
                "method": "POST",
                "data": {
                    "url": url,
                    "name": app_name,
                    "template": "webview"
                }
            },
            "webtoapp": {
                "url": "https://webtoapp.design/api/convert",
                "method": "POST",
                "json": {
                    "website": url,
                    "appName": app_name,
                    "platform": "android"
                }
            }
        }
        
        # Tentar AppsGeyser primeiro
        try:
            print("Tentando AppsGeyser...")
            response = requests.post(
                services["appsgeyser"]["url"],
                data=services["appsgeyser"]["data"],
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    download_url = result.get("download_url")
                    print(f"✅ APK disponível em: {download_url}")
                    return download_url
            
        except Exception as e:
            print(f"AppsGeyser falhou: {e}")
        
        # Tentar WebToApp
        try:
            print("Tentando WebToApp...")
            response = requests.post(
                services["webtoapp"]["url"],
                json=services["webtoapp"]["json"],
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    return result.get("apk_url")
                    
        except Exception as e:
            print(f"WebToApp falhou: {e}")
        
        return None
    
    def create_webapk_manifest(self, url, app_name):
        """Cria WebAPK Manifest (Progressive Web App para Android)"""
        manifest = {
            "name": app_name,
            "short_name": app_name[:12],
            "description": f"App para {url}",
            "start_url": url,
            "display": "standalone",
            "orientation": "portrait",
            "theme_color": "#2196F3",
            "background_color": "#FFFFFF",
            "icons": [
                {
                    "src": "icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png"
                },
                {
                    "src": "icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png"
                }
            ]
        }
        
        return manifest
    
    def create_pwa_wrapper(self, url, app_name):
        """Cria wrapper PWA que pode ser instalado como app"""
        print("📱 Criando PWA Wrapper...")
        
        html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{app_name}</title>
    <meta name="description" content="App para {url}">
    
    <!-- PWA Meta Tags -->
    <meta name="theme-color" content="#2196F3">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="{app_name}">
    
    <!-- Manifest -->
    <link rel="manifest" href="manifest.json">
    
    <!-- Icons -->
    <link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
    <link rel="apple-touch-icon" href="icon-192.png">
    
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            background: #f5f5f5;
        }}
        
        .container {{
            height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        
        .header {{
            background: #2196F3;
            color: white;
            padding: 15px;
            text-align: center;
            font-size: 18px;
            font-weight: bold;
        }}
        
        .webview-container {{
            flex: 1;
            position: relative;
            overflow: hidden;
        }}
        
        #webview {{
            width: 100%;
            height: 100%;
            border: none;
        }}
        
        .loading {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
        }}
        
        .spinner {{
            border: 4px solid #f3f3f3;
            border-top: 4px solid #2196F3;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 2s linear infinite;
            margin: 0 auto 20px;
        }}
        
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        
        .offline {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
            display: none;
        }}
        
        .offline-icon {{
            font-size: 48px;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            {app_name}
        </div>
        <div class="webview-container">
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>Carregando {app_name}...</p>
            </div>
            
            <div class="offline" id="offline">
                <div class="offline-icon">📡</div>
                <h3>Sem conexão</h3>
                <p>Verifique sua conexão com a internet</p>
                <button onclick="location.reload()">Tentar novamente</button>
            </div>
            
            <iframe id="webview" src="{url}" style="display: none;"></iframe>
        </div>
    </div>
    
    <script>
        const webview = document.getElementById('webview');
        const loading = document.getElementById('loading');
        const offline = document.getElementById('offline');
        
        // Verificar conexão
        function checkConnection() {{
            if (!navigator.onLine) {{
                loading.style.display = 'none';
                webview.style.display = 'none';
                offline.style.display = 'block';
                return;
            }}
            
            // Ocultar loading quando carregar
            webview.onload = function() {{
                loading.style.display = 'none';
                webview.style.display = 'block';
            }};
        }}
        
        // Verificar ao carregar
        checkConnection();
        
        // Monitorar mudanças de conexão
        window.addEventListener('online', checkConnection);
        window.addEventListener('offline', checkConnection);
        
        // Registrar Service Worker para funcionar offline
        if ('serviceWorker' in navigator) {{
            navigator.serviceWorker.register('sw.js').then(function(registration) {{
                console.log('ServiceWorker registrado');
            }}).catch(function(err) {{
                console.log('ServiceWorker falhou');
            }});
        }}
    </script>
</body>
</html>"""
        
        # Service Worker para funcionar offline
        sw_content = f"""
const CACHE_NAME = '{app_name}-v1';
const urlsToCache = [
    '/',
    '/manifest.json',
    '/icon-192.png'
];

self.addEventListener('install', function(event) {{
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(function(cache) {{
                return cache.addAll(urlsToCache);
            }})
    );
}});

self.addEventListener('fetch', function(event) {{
    event.respondWith(
        caches.match(event.request)
            .then(function(response) {{
                return response || fetch(event.request);
            }}
        )
    );
}});
"""
        
        # Salvar arquivos
        output_dir = os.path.join(os.getcwd(), f"{app_name.replace(' ', '_')}_PWA")
        os.makedirs(output_dir, exist_ok=True)
        
        with open(os.path.join(output_dir, "index.html"), "w") as f:
            f.write(html_content)
        
        with open(os.path.join(output_dir, "sw.js"), "w") as f:
            f.write(sw_content)
        
        with open(os.path.join(output_dir, "manifest.json"), "w") as f:
            json.dump(self.create_webapk_manifest(url, app_name), f, indent=2)
        
        print(f"✅ PWA criado em: {output_dir}")
        print("📱 Para instalar como app:")
        print("1. Abra index.html no navegador")
        print("2. Clique em 'Adicionar à tela inicial'")
        print("3. O app será instalado como PWA!")
        
        return output_dir
    
    def create_simple_webview_apk(self, url, app_name):
        """Cria APK simples usando WebView no próprio Termux"""
        print("📱 Criando WebView APK simplificado...")
        
        # Script Python que gera APK usando zip
        apk_script = f'''#!/usr/bin/env python3
import zipfile
import os
import tempfile

def create_simple_webview_apk(url, app_name, output_path):
    """Cria APK básico com WebView"""
    
    # Estrutura básica do APK
    apk_files = {{
        "AndroidManifest.xml": f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.termux.webapp">
    
    <uses-permission android:name="android.permission.INTERNET" />
    
    <application
        android:label="{app_name}"
        android:allowBackup="true">
        
        <activity android:name=".MainActivity">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>""",
        
        "classes.dex": b"",  # Classes dex vazias por enquanto
        
        "resources.arsc": b"",  # Recursos vazios
        
        "res/layout/main.xml": f"""<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent">
    
    <WebView
        android:id="@+id/webview"
        android:layout_width="match_parent"
        android:layout_height="match_parent" />
        
</LinearLayout>""",
        
        "res/values/strings.xml": f"""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">{app_name}</string>
</resources>"""
    }}
    
    # Criar APK
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as apk:
        for path, content in apk_files.items():
            if isinstance(content, str):
                content = content.encode('utf-8')
            apk.writestr(path, content)
    
    print(f"APK básico criado: {{output_path}}")
    print("⚠️  Este APK precisaria de classes Java compiladas para funcionar completamente")

# Executar
create_simple_webview_apk("{url}", "{app_name}", "{app_name.replace(' ', '_')}_basic.apk")
'''
        
        with open("create_apk.py", "w") as f:
            f.write(apk_script)
        
        os.system("python create_apk.py")
    
    def run(self):
        """Executa no Termux"""
        print("📱 Termux Web to APK Generator")
        print("=" * 40)
        
        if not self.check_termux():
            print("⚠️  Não detectado ambiente Termux")
            print("Este script é otimizado para Termux Android")
        
        # Instalar dependências
        print("\n1. Instalando dependências...")
        self.install_termux_deps()
        
        # Obter informações
        url = input("\nDigite a URL do site: ").strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        app_name = input("Nome do app: ").strip()
        if not app_name:
            app_name = "WebApp"
        
        print(f"\n🎯 Criando app para: {url}")
        print(f"📱 Nome: {app_name}")
        
        # Opções disponíveis
        print("\n📋 Opções disponíveis:")
        print("1. Criar PWA (Progressive Web App)")
        print("2. Usar serviço cloud")
        print("3. Criar APK básico (experimental)")
        
        opcao = input("\nEscolha (1-3): ").strip()
        
        if opcao == "1":
            self.create_pwa_wrapper(url, app_name)
        elif opcao == "2":
            apk_url = self.use_cloud_service(url, app_name)
            if apk_url:
                print(f"\n✅ APK pronto para download!")
                print(f"📥 URL: {apk_url}")
                print("Use: wget '{apk_url}' -O {app_name}.apk")
            else:
                print("\n❌ Serviços cloud indisponíveis")
                print("Tente a opção PWA!")
        elif opcao == "3":
            self.create_simple_webview_apk(url, app_name)
        else:
            print("Opção inválida!")

if __name__ == "__main__":
    generator = TermuxWebToAPK()
    generator.run()
