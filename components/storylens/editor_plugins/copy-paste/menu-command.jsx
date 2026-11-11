/* AE Scripts menu command template. Installer replaces the two __ markers. */
(function () {
    var root = '__STORYLENS_ROOT__';
    $.evalFile(new File(root + '/editor_plugins/copy-paste/model.js'));
    $.evalFile(new File(root + '/editor_plugins/copy-paste/host.jsx'));
    var action = '__STORYLENS_ACTION__';
    // Binding activation and Off passthrough require an explicit owner choice.
    // This prepared command is not installed or bound by the panel.
    var result = SLCopyPaste.dispatch({action: action});
    if (result.error) alert(result.error, 'Storylens');
})();
