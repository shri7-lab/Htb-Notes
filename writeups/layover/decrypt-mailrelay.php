<?php
$_SERVER['SCRIPT_FILENAME'] = '/var/www/portal/craft';
require '/var/www/portal/bootstrap.php';
$app = require CRAFT_VENDOR_PATH . '/craftcms/cms/bootstrap/console.php';
$val = (new \craft\db\Query())->select(['value'])->from('{{%htbairways_settings}}')->where(['name' => 'mailRelayPassword'])->scalar();
$plain = $app->getSecurity()->decryptByKey(base64_decode($val), $app->getConfig()->getGeneral()->securityKey);
echo 'DECRYPTED:' . $plain . PHP_EOL;
