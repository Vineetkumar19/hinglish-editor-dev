/* Refresh project identity without clearing Copy Paste or import state. */
function storylensProjectId(){var project=app.project,same=false;try{same=storylensPanelProject===project;}catch(_){}if(!same){storylensPanelProject=project;storylensPanelUnsavedId='unsaved-'+new Date().getTime();}return project.file?project.file.fsName:storylensPanelUnsavedId;}
