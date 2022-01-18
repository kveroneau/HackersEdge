updateItems = function(){
  Dajaxice.snippets.get_items(Dajax.process, {'category':$('#category').val()});
}

addItem = function(){
  Dajaxice.snippets.add_item(Dajax.process, {'category':$('#category').val()});
}

saveItem = function(){
  Dajaxice.snippets.save_item(Dajax.process, {'snippet_id':$('#snippet_id').html(),
                                              'title':$('#title').val(),
                                              'content':$('#snippet').val(),
                                              'category':$('#category').val()});
}

getItem = function(snippet_id){
  Dajaxice.snippets.get_item(Dajax.process, {'snippet_id':snippet_id});
  return false;
}