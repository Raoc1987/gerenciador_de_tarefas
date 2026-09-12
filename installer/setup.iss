; Instalador Windows do Gerenciador de Tarefas.
;
; Requer Inno Setup 6.3 ou superior (usa o identificador de arquitetura
; "x64compatible", introduzido nessa versao).
;
; Compilar (depois de `python tools/build.py`):
;
;     python tools/build_installer.py
;     ; ou, diretamente:
;     ISCC.exe /DAppVersion=1.0.0 installer\setup.iss
;
; Produz: installer\Output\GerenciadorDeTarefas-Setup.exe
;
; Regra central: o instalador so mexe nos arquivos DA APLICACAO. O banco de
; dados, as configuracoes e os plugins do utilizador vivem em
; %APPDATA%\GerenciadorDeTarefas e nunca sao tocados na instalacao, na
; atualizacao nem (sem confirmacao explicita) na desinstalacao.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef AppName
  #define AppName "Gerenciador de Tarefas"
#endif
#ifndef AppId
  #define AppId "GerenciadorDeTarefas"
#endif
#ifndef AppPublisher
  #define AppPublisher "Rodrigo Costa"
#endif
#ifndef AppUrl
  #define AppUrl "https://github.com/Raoc1987/gerenciador_de_tarefas"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\GerenciadorDeTarefas"
#endif

[Setup]
; O AppId identifica o produto entre versoes: e o que faz o instalador novo
; reconhecer e atualizar a instalacao existente em vez de duplicar.
AppId={{8F2B6A14-3C7E-4C5A-9E1D-5B0A7D4F2C11}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
VersionInfoVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases

DefaultDirName={autopf}\{#AppId}
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppId}.exe
; Mantem o diretorio escolhido na instalacao anterior ao atualizar.
UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousTasks=yes

; Por omissao instala so para o utilizador atual (sem pedir administrador);
; o utilizador pode escolher instalar para todos no dialogo inicial.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Fecha a aplicacao se estiver aberta, em vez de falhar a copiar os arquivos.
CloseApplications=yes
RestartApplications=no

OutputDir=Output
OutputBaseFilename={#AppId}-Setup
SetupIconFile=..\assets\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Todo o conteudo produzido pelo PyInstaller (executavel, runtime e recursos).
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppId}.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppId}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppId}.exe"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Apaga apenas o que a propria aplicacao gera dentro da pasta de instalacao
; (cache de bytecode); os dados do utilizador estao noutro sitio.
Type: filesandordirs; Name: "{app}\__pycache__"

[Messages]
brazilianportuguese.SetupAppTitle=Instalador
english.SetupAppTitle=Setup
spanish.SetupAppTitle=Instalador

[CustomMessages]
brazilianportuguese.RemoverDados=Deseja remover também os seus dados pessoais (tarefas, configurações e plugins instalados)?%n%nEscolha Não para os manter — é o recomendado se pretende reinstalar o programa.%n%nPasta: %1
english.RemoverDados=Do you also want to remove your personal data (tasks, settings and installed plugins)?%n%nChoose No to keep them — recommended if you plan to reinstall.%n%nFolder: %1
spanish.RemoverDados=¿Desea eliminar también sus datos personales (tareas, configuración y complementos instalados)?%n%nElija No para conservarlos — recomendado si piensa reinstalar.%n%nCarpeta: %1

[Code]
function PastaDeDados(): String;
begin
  { Mesmo caminho que core/paths.py usa: %APPDATA%\GerenciadorDeTarefas }
  Result := ExpandConstant('{userappdata}\{#AppId}');
end;

function RemocaoDeDadosPedidaNaLinhaDeComandos(): Boolean;
begin
  { Para desinstalacao automatizada: unins000.exe /VERYSILENT /REMOVEDATA=yes
    Sem este parametro, uma desinstalacao silenciosa MANTEM sempre os dados. }
  Result := CompareText(ExpandConstant('{param:REMOVEDATA|no}'), 'yes') = 0;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Pasta: String;
begin
  { Os dados do utilizador nunca sao apagados em silencio: so a pedido dele. }
  if CurUninstallStep = usPostUninstall then
  begin
    Pasta := PastaDeDados();
    if DirExists(Pasta) then
    begin
      if RemocaoDeDadosPedidaNaLinhaDeComandos() then
        DelTree(Pasta, True, True, True)
      else if SuppressibleMsgBox(FmtMessage(CustomMessage('RemoverDados'), [Pasta]),
                                 mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
        DelTree(Pasta, True, True, True);
    end;
  end;
end;
