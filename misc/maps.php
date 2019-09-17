<?php
/* Redirect script to let apple users use apple maps and everyone else google maps */
$maps = preg_match("/iPhone|iPad|iPod/i", $_SERVER['HTTP_USER_AGENT']) ? 'maps.apple.com' : 'maps.google.com';
header('Location: https://'.$maps.'/?q='.$_GET['q'])
?>