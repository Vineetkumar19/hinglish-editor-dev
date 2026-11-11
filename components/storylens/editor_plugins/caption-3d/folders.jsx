/* Shared, non-destructive caption project hierarchy. */
(function(global){
 function find(name,parent,owned){for(var i=1;i<=app.project.numItems;i++){var f=app.project.item(i);if(typeof FolderItem!=='undefined'&&!(f instanceof FolderItem))continue;if(f.name===name&&f.parentFolder===parent)return f;}var folder=app.project.items.addFolder(name);folder.parentFolder=parent;folder.comment='Storylens Auto Captions folder';if(owned)owned.push(folder);return folder;}
 function family(name,owned){var root=find('Auto Captions',app.project.rootFolder,owned);return find(name,root,owned);}
 function cleanup(owned){for(var i=owned.length-1;i>=0;i--)try{var item=owned[i];if(item.numItems===0)item.remove();}catch(_){} }
 global.StorylensCaptionFolders={family:family,cleanup:cleanup};
})(typeof $!=='undefined'?$.global:this);
